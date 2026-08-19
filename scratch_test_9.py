import asyncio
import os
import base64

from app.agents import vision_agent

async def run():
    try:
        with open(r'c:\Users\Asus\Desktop\ecosentinel-backend\potholes.jpg', 'rb') as f:
            image_data = f.read()
        
        output, log = await vision_agent.run(image_data, 'image/jpeg')
        print(f"Output: {output}")
        print(f"Log: {log}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
