from pymongo import MongoClient
from PIL import Image
from io import BytesIO

client = MongoClient("mongodb://admin:%40mwte%40mp%4055@191.20.110.47:27019/myDb?authSource=admin")
db = client["image_database"]
collection = db["images"]

def fetch_and_display_image(filename):
    try:
        document = collection.find_one({"filename": filename})
        if document:
            image_data = document["image"]
            image = Image.open(BytesIO(image_data))

            image.show()
            print(f"Image '{filename}' has been found and displayed.")
        else:
            print(f"Image '{filename}' not found in MongoDB.")
    
    except Exception as e:
        print(f"Error: {e}")

fetch_and_display_image("128858_0.jpg")