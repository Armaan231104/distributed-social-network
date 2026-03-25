import base64

def encode_image(entry):
    if not entry.image:
        return None
    
    with entry.image.open("rb") as img:
        return base64.b64encode(img.read()).decode("utf-8")