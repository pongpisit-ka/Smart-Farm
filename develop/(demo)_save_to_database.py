from pymongo import MongoClient

client = MongoClient("mongodb://admin:%40mwte%40mp%4055@191.20.110.47:27019/myDb?authSource=admin")
db = client["image_database"]
collection = db["images"]

def save_image_to_mongodb(image_path):
    try:
        with open(image_path, "rb") as image_file:
            image_data = image_file.read()  
        
        document = {
            "filename": image_path.split("\\")[-1],  
            "image": image_data 
        }
 
        collection.insert_one(document)
        print(f"Image '{image_path}' has been saved to MongoDB.")
    
    except Exception as e:
        print(f"Error: {e}")

save_image_to_mongodb(r"D:\smartfarm\picture\128858_0.jpg")