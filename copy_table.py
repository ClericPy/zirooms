import pyperclip

with open('data.txt', encoding='u8') as f:
    pyperclip.copy(f.read())
