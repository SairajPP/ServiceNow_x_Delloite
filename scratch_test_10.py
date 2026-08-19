import asyncio
import os
import base64
from openai import AsyncOpenAI

async def run():
    client = AsyncOpenAI(
        api_key=os.environ.get('NVIDIA_API_KEY', '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'),
        base_url='https://integrate.api.nvidia.com/v1'
    )
    try:
        with open(r'c:\Users\Asus\Desktop\ecosentinel-backend\potholes.jpg', 'rb') as f:
            image_data = f.read()
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{base64_image}"

        print("Testing 11b model...")
        resp = await client.chat.completions.create(
            model='meta/llama-3.2-11b-vision-instruct',
            messages=[{
                'role': 'user', 
                'content': [
                    {'type': 'text', 'text': 'what is this'}, 
                    {'type': 'image_url', 'image_url': {'url': image_url}}
                ]
            }], 
            max_tokens=50,
            timeout=10.0
        )
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
