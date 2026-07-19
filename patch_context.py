file_path = './env/lib/python3.14/site-packages/django/template/context.py'
with open(file_path, 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'def __copy__(self):' in line:
        new_lines.append('    def __copy__(self):\n')
        new_lines.append('        duplicate = self.__class__.__new__(self.__class__)\n')
        new_lines.append('        duplicate.__dict__.update(self.__dict__)\n')
        new_lines.append('        duplicate.dicts = self.dicts[:]\n')
        new_lines.append('        return duplicate\n')
        skip = True
        continue
    if skip:
        if 'return duplicate' in line:
            skip = False
        continue
    new_lines.append(line)

with open(file_path, 'w') as f:
    f.writelines(new_lines)
