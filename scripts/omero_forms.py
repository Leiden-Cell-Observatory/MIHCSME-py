import json
from omero_forms_client import OMEROFormsClient

# Initialize client
client = OMEROFormsClient(
    base_url='http://localhost:4080',
    username='root',
    password='omero'
)

# Login
client.login()

# Your form details
form_id = 'Fun'
dataset_id = 1

# Prepare test data
test_data = {
    "firstName": "Maarten",
    "lastName": "Paul",
    "age": 32,
    "bio": "Bioimage analysis researcher at LACDR"
}

# Save form data
print(f"=== Saving Form Data to Dataset {dataset_id} ===")
try:
    response = client.save_form_data(
        form_id=form_id,
        obj_type='Dataset',
        obj_id=dataset_id,
        metadata_dict=test_data,
        message=""
    )
    
    if response is None:
        print("✓ Data saved successfully (server returned empty response)")
    else:
        print("✓ Data saved successfully")
        print(json.dumps(response, indent=2))
        
except Exception as e:
    print(f"✗ Error saving form data: {e}")

# Verify by retrieving the data
print(f"\n=== Verifying Saved Data ===")
try:
    retrieved_data = client.get_form_data(
        form_id=form_id,
        obj_type='Dataset',
        obj_id=dataset_id
    )
    
    print("✓ Successfully retrieved data:")
    
    # Parse the form data
    form_data = json.loads(retrieved_data['data']['formData'])
    print(f"  First Name: {form_data.get('firstName')}")
    print(f"  Last Name: {form_data.get('lastName')}")
    print(f"  Age: {form_data.get('age')}")
    print(f"  Bio: {form_data.get('bio')}")
    print(f"  Saved by user ID: {retrieved_data['data']['changedBy']}")
    print(f"  Saved at: {retrieved_data['data']['changedAt']}")
    print(f"  Message: {retrieved_data['data']['message']}")
    
except Exception as e:
    print(f"✗ Error retrieving form data: {e}")

# Logout
client.logout()