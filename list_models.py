import google.generativeai as genai

API_KEY = "AIzaSyBln7UMxEwvuHjWDeV390plGbrxR677_34"
genai.configure(api_key=API_KEY)

print("Listing models:")
for m in genai.list_models():
  if 'generateContent' in m.supported_generation_methods:
    print(m.name)
