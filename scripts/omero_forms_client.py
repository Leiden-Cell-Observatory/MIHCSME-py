import requests
import json
from datetime import datetime
from typing import Dict, List, Optional, Any


class OMEROFormsClient:
    """Client for interacting with OMERO.web and OMERO.forms plugin"""
    
    def __init__(self, base_url, username, password, server_id=1):
        """
        Initialize OMERO.forms client
        
        Args:
            base_url: OMERO.web base URL (e.g., 'http://localhost:4080')
            username: OMERO username
            password: OMERO password
            server_id: Server index (default: 1)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.server_id = server_id
        self.session = requests.Session()
        self.api_version = '0'
        
    def login(self):
        """Authenticate with OMERO.web"""
        # Get CSRF token
        token_url = f'{self.base_url}/api/v{self.api_version}/token/'
        response = self.session.get(token_url)
        response.raise_for_status()
        
        csrf_token = self.session.cookies.get('csrftoken')
        
        # Login
        login_url = f'{self.base_url}/api/v{self.api_version}/login/'
        login_data = {
            'username': self.username,
            'password': self.password,
            'server': self.server_id,
            'csrfmiddlewaretoken': csrf_token
        }
        
        headers = {
            'X-CSRFToken': csrf_token,
            'Referer': self.base_url
        }
        
        response = self.session.post(login_url, data=login_data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        if not result.get('success'):
            raise Exception(f"Login failed: {result.get('message', 'Unknown error')}")
        
        print(f"Successfully logged in as {self.username}")
        return result
    
    def list_forms(self) -> List[Dict]:
        """Get list of all available forms"""
        url = f'{self.base_url}/omero_forms/list_forms/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def list_applicable_forms(self, obj_type: str) -> List[Dict]:
        """
        Get forms applicable to a specific object type
        
        Args:
            obj_type: OMERO object type (e.g., 'Dataset', 'Image', 'Project')
        """
        url = f'{self.base_url}/omero_forms/list_applicable_forms/{obj_type}/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_form(self, form_id: str) -> Dict:
        """
        Get form definition (latest version)
        
        Args:
            form_id: Form identifier (e.g., 'REMBI_Biosample')
        """
        url = f'{self.base_url}/omero_forms/get_form/{form_id}/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_form_data(self, form_id: str, obj_type: str, obj_id: int) -> Dict:
        """
        Get existing form data for an object
        
        Args:
            form_id: Form identifier
            obj_type: OMERO object type
            obj_id: OMERO object ID
        """
        url = f'{self.base_url}/omero_forms/get_form_data/{form_id}/{obj_type}/{obj_id}/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def get_form_data_history(self, form_id: str, obj_type: str, obj_id: int) -> Dict:
        """
        Get complete history of form data for an object
        
        Args:
            form_id: Form identifier
            obj_type: OMERO object type
            obj_id: OMERO object ID
        """
        url = f'{self.base_url}/omero_forms/get_form_data_history/{form_id}/{obj_type}/{obj_id}/'
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def save_form_data(self, form_id: str, obj_type: str, obj_id: int, 
                    metadata_dict: Dict, message: str = "") -> Optional[Dict]:
        """
        Save form data with correct form version timestamp
        """
        csrf_token = self.session.cookies.get('csrftoken')
        
        # Get the form definition to use its timestamp
        form_def = self.get_form(form_id)
        form_timestamp = form_def['form']['timestamp']  # Use the form's timestamp!
        
        url = f'{self.base_url}/omero_forms/save_form_data/{form_id}/{obj_type}/{obj_id}/'
        
        # Use compact JSON format (no spaces)
        data_json = json.dumps(metadata_dict, separators=(',', ':'))
        
        payload = {
            'data': data_json,
            'formTimestamp': form_timestamp,  # Use form's timestamp, not current time
            'message': message
        }
        
        headers = {
            'X-CSRFToken': csrf_token,
            'Referer': self.base_url,
            'Content-Type': 'application/json'
        }
        
        response = self.session.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        if response.text:
            try:
                return response.json()
            except json.JSONDecodeError:
                return None
        else:
            return None
    
    def logout(self):
        """Logout from OMERO.web"""
        logout_url = f'{self.base_url}/webclient/logout/'
        self.session.get(logout_url)
        print("Logged out successfully")