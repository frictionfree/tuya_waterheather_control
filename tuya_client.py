import os
import requests
import time
import hashlib
import hmac
import json
import urllib
from typing import Optional, Tuple, Dict, Any

class TuyaClient:
    def __init__(self):
        self.access_id = os.environ.get('TUYA_ACCESS_ID')
        self.access_secret = os.environ.get('TUYA_ACCESS_SECRET') 
        self.device_id = os.environ.get('TUYA_DEVICE_ID')
        self.region_endpoint = os.environ.get('TUYA_REGION_ENDPOINT', 'https://openapi.tuyaeu.com')
        
        self.timeout = 15
        self._access_token = None
        self._token_expires = 0
        
        # Validate required environment variables
        if not all([self.access_id, self.access_secret, self.device_id]):
            raise ValueError("Missing required Tuya environment variables")

    def _sha256_hex(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _canonical_path_with_query(self, path: str, query: Optional[Dict] = None) -> str:
        if not query:
            return path
        qs = urllib.parse.urlencode(sorted(query.items()), doseq=True)
        return f"{path}?{qs}"

    def _build_sign(self, secret: str, client_id: str, access_token: Optional[str], 
                    t_ms: str, method: str, path: str, query: Optional[Dict], 
                    body_bytes: bytes) -> str:
        content_hash = self._sha256_hex(body_bytes)
        string_to_sign = "\n".join([
            method.upper(), 
            content_hash, 
            "", 
            self._canonical_path_with_query(path, query)
        ])
        base = client_id + (access_token or "") + t_ms + string_to_sign
        return hmac.new(secret.encode(), base.encode(), hashlib.sha256).hexdigest().upper()

    def _build_headers(self, client_id: str, sign: str, t_ms: str, 
                      access_token: Optional[str] = None, extra: Optional[Dict] = None) -> Dict[str, str]:
        headers = {
            "client_id": client_id,
            "sign": sign,
            "t": t_ms,
            "sign_method": "HMAC-SHA256",
        }
        if access_token:
            headers["access_token"] = access_token
        if extra:
            headers.update(extra)
        return headers

    def _tuya_get(self, path: str, query: Optional[Dict] = None, 
                  access_token: Optional[str] = None) -> Dict[str, Any]:
        t = str(int(time.time() * 1000))
        sign = self._build_sign(self.access_secret, self.access_id, access_token, 
                               t, "GET", path, query, b"")
        url = f"{self.region_endpoint}{path}"
        
        response = requests.get(
            url, 
            params=query, 
            headers=self._build_headers(self.access_id, sign, t, access_token),
            timeout=self.timeout
        )
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"GET {path} failed: {result}")
        return result

    def _tuya_post(self, path: str, payload: Dict[str, Any], access_token: str) -> Dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode()
        t = str(int(time.time() * 1000))
        sign = self._build_sign(self.access_secret, self.access_id, access_token,
                               t, "POST", path, None, body)
        url = f"{self.region_endpoint}{path}"
        
        headers = self._build_headers(self.access_id, sign, t, access_token, 
                                     {"Content-Type": "application/json"})
        
        response = requests.post(url, headers=headers, data=body, timeout=self.timeout)
        response.raise_for_status()
        
        result = response.json()
        if not result.get("success"):
            raise RuntimeError(f"POST {path} failed: {result}")
        return result

    def _get_access_token(self) -> str:
        """Get or refresh access token"""
        current_time = int(time.time())
        
        # Return cached token if still valid (with 5 min buffer)
        if self._access_token and current_time < (self._token_expires - 300):
            return self._access_token
        
        # Get new token
        result = self._tuya_get("/v1.0/token", {"grant_type": "1"})
        self._access_token = result["result"]["access_token"]
        self._token_expires = current_time + result["result"]["expire_time"]
        
        return self._access_token

    def _find_switch_code(self, status_list: list, access_token: str) -> Tuple[str, Optional[bool]]:
        """Find the device's power switch code and current value"""
        # Try from current status first
        for item in status_list:
            code = item.get("code", "")
            if code == "switch" or code.startswith("switch_"):
                if isinstance(item.get("value"), bool):
                    return code, bool(item["value"])

        # If not found in status, try functions
        result = self._tuya_get(f"/v1.0/devices/{self.device_id}/functions", 
                               access_token=access_token)
        functions = result["result"]["functions"]
        
        # Prefer plain 'switch', else first switch_*
        candidate = None
        for func in functions:
            if func.get("code") == "switch":
                candidate = "switch"
                break
            if func.get("code", "").startswith("switch_"):
                candidate = func["code"]
        
        if not candidate:
            raise RuntimeError("No switch datapoint found in device functions")
        
        return candidate, None

    def get_device_status(self) -> Dict[str, Any]:
        """Get current device status"""
        access_token = self._get_access_token()
        result = self._tuya_get(f"/v1.0/devices/{self.device_id}/status", 
                               access_token=access_token)
        return result["result"]

    def set_device_state(self, target_state: bool) -> Dict[str, Any]:
        """Set device ON/OFF state"""
        access_token = self._get_access_token()
        
        # Get current status to find switch code
        status_list = self.get_device_status()
        switch_code, current_state = self._find_switch_code(status_list, access_token)
        
        # If we don't have current state, query again
        if current_state is None:
            status_list = self.get_device_status()
            current_state = next((s["value"] for s in status_list 
                                if s.get("code") == switch_code), None)
        
        # Skip if already in target state
        if current_state == target_state:
            return {
                "skipped": True,
                "reason": f"Device already {'ON' if target_state else 'OFF'}",
                "switch_code": switch_code,
                "current_state": current_state
            }
        
        # Send command
        payload = {"commands": [{"code": switch_code, "value": target_state}]}
        result = self._tuya_post(f"/v1.0/devices/{self.device_id}/commands", 
                                payload, access_token)
        
        return {
            "success": True,
            "switch_code": switch_code,
            "previous_state": current_state,
            "target_state": target_state,
            "response": result
        }

    def verify_device_state(self, expected_state: bool, max_retries: int = 3) -> bool:
        """Verify device is in expected state with retries"""
        for attempt in range(max_retries):
            try:
                status_list = self.get_device_status()
                access_token = self._get_access_token()
                switch_code, current_state = self._find_switch_code(status_list, access_token)
                
                if current_state == expected_state:
                    return True
                    
                if attempt < max_retries - 1:
                    time.sleep(2)  # Brief wait before retry
                    
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    
        return False

    def ensure_state_with_retries(self, target_state: bool, max_attempts: int = 5) -> Dict[str, Any]:
        """Ensure device is in target state with retries (for eventual consistency)"""
        attempts = 0
        last_result = None
        
        while attempts < max_attempts:
            try:
                result = self.set_device_state(target_state)
                
                if result.get("skipped"):
                    return result  # Already in correct state
                
                # Wait and verify
                time.sleep(6)
                if self.verify_device_state(target_state):
                    return {
                        "success": True,
                        "attempts": attempts + 1,
                        "verified": True,
                        "last_result": result
                    }
                
                last_result = result
                attempts += 1
                
            except Exception as e:
                attempts += 1
                last_result = {"error": str(e), "attempt": attempts}
                if attempts < max_attempts:
                    time.sleep(6)
        
        return {
            "success": False,
            "attempts": attempts,
            "verified": False,
            "last_result": last_result
        }