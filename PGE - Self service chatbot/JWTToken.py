import jwt
from datetime import datetime, timedelta

def create_jwt_token(payload):
    # Your secret key (guard it with your life!)
    secret_key = 'ERMN05OPLoDvbTTa/QkqLNMI7cPLguaRyHzyg7n5qNBVjQmtBhz4SzYh4NBVCXi3KJHlSXKP+oi2+bXr6CUYTR=='
    # Algorithm for token generation
    algorithm = 'HS256'
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token

def validate_jwt_token(token_to_validate):
    secret_key = 'ERMN05OPLoDvbTTa/QkqLNMI7cPLguaRyHzyg7n5qNBVjQmtBhz4SzYh4NBVCXi3KJHlSXKP+oi2+bXr6CUYTR=='
    algorithm = 'HS256'
    try:
        decoded_payload = jwt.decode(token_to_validate, secret_key, algorithms=[algorithm])
        return decoded_payload
    except jwt.ExpiredSignatureError:
        print("Token has expired. Please log in again.")
    except jwt.InvalidTokenError:
        print("Invalid token. Access denied.")
    return None

def main():
    # payload = {
    #     'user_id': 151627,
    #     'username': 'Sudharani Nagarajan',
    #     # 'role': 'mouse_catcher',
    #     'exp': datetime.now() + timedelta(minutes=30) # Token will expire in 1 hour
    # }
    # print("JWT TOKEN: ", create_jwt_token(payload))

    token_to_validate = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxNTE2MjcsInVzZXJuYW1lIjoiU3VkaGFyYW5pIE5hZ2FyYWphbiIsImV4cCI6MTczMDg5MzMzM30.NhXoionS11NabEsnVKVJpLyEqcW2CkJTYA5c4kun-Uo'
    # Validate and decode the token
    decoded_payload = validate_jwt_token(token_to_validate)
    if decoded_payload:
        # If the decoding is successful, you can trust the token!
        print("Decoded Payload:", decoded_payload)
        emdid = decoded_payload['user_id']
        
        print(emdid)

if __name__ == "__main__":
    main()