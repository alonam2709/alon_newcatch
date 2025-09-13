"""
MCP Server Template
"""

from mcp.server.fastmcp import FastMCP
from pydantic import Field
import mcp.types as types
import boto3
import os
import uuid
from datetime import datetime

# Initialize S3 client
s3_client = boto3.clieSnt(
    's3',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name=os.environ.get('AWS_REGION', 'eu-north-1')
)
BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'voice-recordings-catchmeow')

mcp = FastMCP("Echo Server", port=3000, stateless_http=True, debug=True)


@mcp.tool(
    title="Echo Tool",
    description="Echo the input text",
)
def echo(text: str = Field(description="The text to echo")) -> str:
    return text


@mcp.tool(
    title="Generate S3 Upload URL",
    description="Generate a presigned URL for uploading audio files to S3"
)
def generate_upload_url(filename: str = Field(description="The filename for the audio file")) -> dict:
    """Generate a presigned URL for uploading files to S3"""
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        s3_key = f"recordings/{timestamp}_{unique_id}_{filename}"
        
        # Generate presigned URL for PUT operation
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': s3_key,
                'ContentType': 'audio/wav'
            },
            ExpiresIn=86400  # URL expires in 24 hours
        )
        
        return {
            "upload_url": presigned_url,
            "s3_key": s3_key,
            "filename": filename
        }
    except Exception as e:
        return {"error": f"Failed to generate upload URL: {str(e)}"}


@mcp.resource(
    uri="greeting://{name}",
    description="Get a personalized greeting",
    name="Greeting Resource",
)
def get_greeting(
    name: str,
) -> str:
    return f"Hello, {name}!"


@mcp.prompt("")
def greet_user(
    name: str = Field(description="The name of the person to greet"),
    style: str = Field(description="The style of the greeting", default="friendly"),
) -> str:
    """Generate a greeting prompt"""
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
        "casual": "Please write a casual, relaxed greeting",
    }

    return f"{styles.get(style, styles['friendly'])} for someone named {name}."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")