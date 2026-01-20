# from omero_forms_client import OMEROFormsClient
# import json

# client = OMEROFormsClient(
#     base_url='http://localhost:4080',
#     username='root',
#     password='omero'
# )
# client.login()

# # Compare the stored data structure
# print("=== Dataset 52 (Manual - Works) ===")
# manual = client.get_form_data('Fun', 'Dataset', 52)
# print(json.dumps(manual, indent=2))

# print("\n=== Dataset 1 (Script - Crashes) ===")
# script = client.get_form_data('Fun', 'Dataset', 1)
# print(json.dumps(script, indent=2))

# print("\n=== Comparison ===")
# print(f"Manual formId: {manual['data'].get('formId')}")
# print(f"Script formId: {script['data'].get('formId')}")
# print(f"Match? {manual['data'].get('formId') == script['data'].get('formId')}")

# print(f"\nManual formData type: {type(manual['data'].get('formData'))}")
# print(f"Script formData type: {type(script['data'].get('formData'))}")

# # Parse the formData JSON
# manual_parsed = json.loads(manual['data']['formData'])
# script_parsed = json.loads(script['data']['formData'])

# print(f"\nManual formData keys: {manual_parsed.keys()}")
# print(f"Script formData keys: {script_parsed.keys()}")

# client.logout()

from omero_forms_client import OMEROFormsClient

client = OMEROFormsClient(
    base_url='http://localhost:4080',
    username='root',
    password='omero'
)
client.login()

# Get the form to check its timestamp
form_def = client.get_form('Fun')
print(f"Form timestamp: {form_def['form']['timestamp']}")

# Save data with correct timestamp
test_data = {
    "firstName": "Maarten",
    "lastName": "Paul",
    "age": 40,
    "bio": "Testing with correct form timestamp"
}

client.save_form_data(
    form_id='Fun',
    obj_type='Dataset',
    obj_id=1,  # Update dataset 1
    metadata_dict=test_data,
    message="Fixed timestamp test"
)

print("✓ Data saved with form timestamp")

# Verify
saved = client.get_form_data('Fun', 'Dataset', 1)
print(f"\nSaved formTimestamp: {saved['data']['formTimestamp']}")

# Test history
print("\n=== Testing History View ===")
print("Now try viewing the history in the browser for Dataset 1")
print("It should work now!")

client.logout()