import requests
import json

# Test the MCP server tools
def test_mcp_tools():
    base_url = "http://127.0.0.1:3000"
    
    print("🧪 Testing MCP Server...")
    
    # Test 1: Check S3 Connection
    print("\n1️⃣ Testing S3 Connection...")
    try:
        response = requests.post(
            f"{base_url}/tools/check_s3_connection",
            headers={"Content-Type": "application/json"},
            json={"arguments": {}}
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ S3 Connection Test Result:")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
    
    # Test 2: Generate Upload URL
    print("\n2️⃣ Testing Upload URL Generation...")
    try:
        response = requests.post(
            f"{base_url}/tools/generate_upload_url",
            headers={"Content-Type": "application/json"},
            json={"arguments": {"filename": "test_recording.wav"}}
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ Upload URL Generated:")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Upload URL generation failed: {e}")
    
    # Test 3: List Recordings
    print("\n3️⃣ Testing List Recordings...")
    try:
        response = requests.post(
            f"{base_url}/tools/list_recordings",
            headers={"Content-Type": "application/json"},
            json={"arguments": {}}
        )
        if response.status_code == 200:
            result = response.json()
            print("✅ Current Recordings:")
            print(json.dumps(result, indent=2))
        else:
            print(f"❌ Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ List recordings failed: {e}")

if __name__ == "__main__":
    test_mcp_tools()