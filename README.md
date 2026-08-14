# python_code_snippets

## arr_nums insert / delete / replace

`array_operations.py` is a small application around `arr_nums`, a list of
**15,335** elements. It inserts, deletes, and replaces values at chosen
indexes, with bounds checks and typed errors.

### Run the scripted demonstration

```bash
python3 array_operations.py
python3 array_operations.py demo
```

### Interactive application

```bash
python3 array_operations.py interactive
```

Example session:

```text
arr_nums[15335]> insert 0 HEAD
arr_nums[15336]> replace 100 42
arr_nums[15336]> delete -1
arr_nums[15335]> show 0 10
arr_nums[15335]> quit
```

Type `help` inside the prompt for the full command list.

### One-shot commands

```bash
python3 array_operations.py insert 0 HEAD
python3 array_operations.py delete -- -1
python3 array_operations.py replace 100 42
python3 array_operations.py get 0
python3 array_operations.py show 0 10
python3 array_operations.py append 99
python3 array_operations.py find 654
```

`--size`, `--seed`, and `--values` control the starting array:

```bash
python3 array_operations.py --values 10,20,30 insert 1 99
```

Negative indexes on the command line need `--` so argparse does not treat
them as flags: `delete -- -1`.

### Tests

```bash
python3 -m unittest test_array_operations.py -v
```
