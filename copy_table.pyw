import pyperclip
import winsound

with open('data.txt', encoding='u8') as f:
    source = f.read()
    pyperclip.copy(source + '\n' * max([100, source.count('\n')]))
for _ in range(5):
    winsound.Beep(900, 300)
