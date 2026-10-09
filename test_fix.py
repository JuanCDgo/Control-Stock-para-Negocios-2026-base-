with open('app.py', 'rb') as f:
    b = f.read()
if b.startswith(b'\xef\xbb\xbf'):
    b = b[3:]
text = b.decode('utf-8')

try:
    original_bytes = text.encode('latin1')
    print("Success with latin1")
except Exception as e:
    print(f"Error latin1: {e}")
