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

## tree_nums insert / delete / replace

`tree_operations.py` is the same set of operations on a **binary tree ADT**.
`tree_nums` is a complete binary tree of **15,335** nodes by default. Nodes
are addressed by level-order index (root is 0, left child of `i` is
`2*i+1`, right child is `2*i+2`).

- **insert** adds a child of an existing node (left slot first)
- **delete** removes one node: a leaf is unlinked, one child is promoted,
  two children lift the inorder successor
- **replace** changes a node's value and leaves the shape alone

```bash
python3 tree_operations.py
python3 tree_operations.py interactive
python3 tree_operations.py --values 4,2,6,1,3,5,7 show
python3 tree_operations.py --values 4,2,6 append 1
python3 tree_operations.py --values 4,2,6,1,3,5,7 delete 0
python3 tree_operations.py --values 4,2,6,1,3,5,7 replace 0 99
python3 -m unittest test_tree_operations.py -v
```

Inside interactive mode, type `help` for `insert-left`, `insert-right`,
`delete-subtree`, and the traversal commands.

## Bookstore sorting (bubble, selection, insertion, merge)

`sorting_algorithms.py` sorts a **Riverside Campus Bookstore** inventory
so students can view flash-sale titles from cheapest to most expensive.

- **Bubble sort** — clerks swap adjacent books until the shelf is clean
- **Selection sort** — pick the cheapest remaining title for the next slot
- **Insertion sort** — unpack one book at a time onto an already-sorted shelf
- **Merge sort** — two teams sort half the 15,335-SKU catalog, then merge

Two Python books share a $79.99 price so the demo can show which
algorithms are stable.

```bash
python3 sorting_algorithms.py
python3 sorting_algorithms.py interactive
python3 sorting_algorithms.py sort --algorithm merge --by price
python3 sorting_algorithms.py sort --algorithm insertion --size 20
python3 -m unittest test_sorting_algorithms.py -v
```

## Advanced Python features (Riverside Student Swap)

`campus_marketplace.py` is a campus buy/sell desk that uses the language
features together on one job: Maya shops used textbooks, staff pick bins,
then checkout applies coupons and tax.

| Feature | Where it shows up |
| --- | --- |
| **list** | cart, undo stack, SKUs in a bin |
| **dict** | SKU → listing; `(building, aisle, bin)` → bin contents |
| **tuple** | immutable warehouse coordinate and dict key |
| **set** | listing tags, claimed students, interest ∩ tags |
| **list comprehension** | search hits, items under $20, pick stops |
| **generator** | `iter_catalog()`, `low_stock_alerts()` (`yield` / `yield from`) |
| **decorator** | `@timed`, `@audit`, `@require_sku` |
| **iterator** | `PickRoute` (`__iter__`, `__next__`) |
| **callable** | `PercentageOff` (`__call__`) stacked coupons |
| **closure** | `make_tax_calculator(0.0825)`, `make_budget_filter(25)` |
| **`__repr__` / `__str__` / `__eq__`** | debugger dump, shelf label, SKU identity |

```bash
python3 campus_marketplace.py
python3 -m unittest test_campus_marketplace.py -v
```

## Hash map (campus ID office)

`hashmap.py` is a **separate-chaining hash table** — not Python's `dict`.
The demo is the Riverside ID office: tap a student ID, hash it, jump to
the meal-plan / locker record. Colliding SIDs share a bucket chain;
the table doubles when the load factor crosses 0.75.

```bash
python3 hashmap.py
python3 hashmap.py lookup R1002341
python3 -m unittest test_hashmap.py -v
```

## Graph algorithms (shuttle + course planner)

`graph_algorithms.py` is an adjacency-list graph with BFS, DFS,
Dijkstra, topological sort, connected components, and cycle detection.

- **Shuttle map** (undirected, weighted): fewest hops vs fastest ride.
  Union → Health is one express hop (20 min) but the local three-hop
  route is 15 minutes — BFS and Dijkstra disagree on purpose.
- **Degree planner** (directed): a legal semester order from
  prerequisites; a cycle in the catalog is rejected.

```bash
python3 graph_algorithms.py
python3 graph_algorithms.py path Union Health
python3 graph_algorithms.py plan
python3 -m unittest test_graph_algorithms.py -v
```

## Riverside Campus Hub (everything together)

`riverside_hub.py` is the comprehensive application. Maya Chen's morning
runs through every module in this repo: ID tap (hash map), advising
waitlist (array), campus directory (tree), flash-sale prices (merge
sort), used-book checkout (marketplace), shuttle routing (BFS vs
Dijkstra), and a CS degree plan (topological sort).

```bash
python3 riverside_hub.py
python3 riverside_hub.py tap R1002341
python3 riverside_hub.py ride Union Health
python3 riverside_hub.py interactive
python3 -m unittest test_riverside_hub.py -v
```

## Education metrics — Charles County Public Schools (`edumetrics/`)

A production-style metrics package for the CCPS district (North Point,
La Plata, Thomas Stone, Westlake, etc.) measuring three pillars:

- **Students** — attendance, chronic absenteeism (< 90%), GPA, MCAP
  proficiency (levels 3-4), and growth percentiles from fall/spring scores
- **Teachers** — composite of median student growth (50%), Danielson-style
  evaluation (30%), and PD hours (20%), banded into effectiveness ratings
- **Curriculum** — MD standards coverage, assessment alignment, pacing
  variance, and course pass rates, with untaught standards listed
- **Equity** — FARMS / ELL / IEP proficiency gaps, flagged past 10 points

All records validate on construction and the district cross-checks
foreign keys, so bad rows fail at load time rather than mid-report.
Data is a deterministic synthetic generator (`--seed`); swap in a real
SIS/CSV export without touching the metrics.

```bash
python3 -m edumetrics district
python3 -m edumetrics school "North Point High"
python3 -m edumetrics teachers --school "La Plata High" --top 5
python3 -m edumetrics curriculum
python3 -m edumetrics equity --subject Math
python3 -m edumetrics export --out ccps_report.json
python3 -m unittest test_edumetrics.py -v
```

### Dashboards (Tcl/Tk GUI and Textual TUI)

Two front-ends render the same metrics through `edumetrics/views.py`:

- **`edumetrics_tk.py`** — native Tcl/Tk window (tkinter). Notebook tabs
  for Schools / Teachers / Curriculum / Equity, click-to-sort column
  headers, a school dropdown that filters the Teachers tab, scrollbars,
  and shortcuts: `Ctrl+1..4` tabs, `Ctrl+R` reload, `Ctrl+E` export,
  `Ctrl+Q` quit. Needs a display (`sudo apt-get install python3-tk`).
- **`edumetrics_tui.py`** — Textual/Rich terminal dashboard with full
  keyboard **and mouse** support (click tabs, wheel-scroll tables).
  Keys: `1-4` tabs, `r` reload, `x` export JSON, `q` quit.
  Install with `pip install -r requirements.txt`.

```bash
python3 edumetrics_tui.py          # terminal dashboard
python3 edumetrics_tk.py           # desktop window
python3 -m unittest test_metrics_frontends.py -v
```





