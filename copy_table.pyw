import pyperclip
import winsound

with open('data.txt', encoding='u8') as f:
    source = f.read().strip()
    pyperclip.copy(source + '\n\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t' * max([100, source.count('\n')]))
for _ in range(2):
    winsound.Beep(900, 300)
