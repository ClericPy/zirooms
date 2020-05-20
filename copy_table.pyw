import pyperclip
import winsound

with open('data.txt', encoding='u8') as f:
    pyperclip.copy(f.read())
for _ in range(5):
    winsound.Beep(900, 300)
