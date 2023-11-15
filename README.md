# dataframe fs

Dataframes everywhere for everything.
Similar to /proc except everything is an arrow dataframe able to be used by any language/tool that can read ipc format.
Currently using osquery as a quick way to pull tables of os data.

## Usage

```
$ mkdir test
$ ./dffs.py test

$ python3
>>> import polars as pl
>>> df_mounts = pl.read_json("test/mounts.json")
>>> df_mounts
shape: (88, 11)
┌─────────┬──────────────────┬─────────────┬─────────────┬───┬─────────┬─────────────┬─────────────────────┬──────────┐
│ blocks  ┆ blocks_available ┆ blocks_free ┆ blocks_size ┆ … ┆ inodes  ┆ inodes_free ┆ path                ┆ type     │
│ ---     ┆ ---              ┆ ---         ┆ ---         ┆   ┆ ---     ┆ ---         ┆ ---                 ┆ ---      │
│ str     ┆ str              ┆ str         ┆ str         ┆   ┆ str     ┆ str         ┆ str                 ┆ str      │
╞═════════╪══════════════════╪═════════════╪═════════════╪═══╪═════════╪═════════════╪═════════════════════╪══════════╡
│ 0       ┆ 0                ┆ 0           ┆ 4096        ┆ … ┆ 0       ┆ 0           ┆ /sys                ┆ sysfs    │
│ 0       ┆ 0                ┆ 0           ┆ 4096        ┆ … ┆ 0       ┆ 0           ┆ /proc               ┆ proc     │
│ 4070321 ┆ 4070321          ┆ 4070321     ┆ 4096        ┆ … ┆ 4070321 ┆ 4069469     ┆ /dev                ┆ devtmpfs │
│ 0       ┆ 0                ┆ 0           ┆ 4096        ┆ … ┆ 0       ┆ 0           ┆ /dev/pts            ┆ devpts   │
│ …       ┆ …                ┆ …           ┆ …           ┆ … ┆ …       ┆ …           ┆ …                   ┆ …        │
│ 1923    ┆ 0                ┆ 0           ┆ 131072      ┆ … ┆ 715     ┆ 0           ┆ /snap/firefox/3358  ┆ squashfs │
│ 4080470 ┆ 4080470          ┆ 4080470     ┆ 4096        ┆ … ┆ 4080470 ┆ 4080469     ┆ /run/qemu           ┆ tmpfs    │
│ 782     ┆ 0                ┆ 0           ┆ 131072      ┆ … ┆ 315     ┆ 0           ┆ /snap/discord/163   ┆ squashfs │
│ 4096    ┆ 2048             ┆ 0           ┆ 512         ┆ … ┆ 0       ┆ 0           ┆ /home/aaron/codebas ┆ fuse     │
│         ┆                  ┆             ┆             ┆   ┆         ┆             ┆ es/dffs/test        ┆          │
└─────────┴──────────────────┴─────────────┴─────────────┴───┴─────────┴─────────────┴─────────────────────┴──────────┘
>>>

>>> df_mounts = pl.read_ipc("test/mounts.arrow")
```


## Known issues

* OutOfSpec("InvalidFooter") errors on first load of arrow table

Just load the same table again and it works the second time.

```
>>> pl.read_ipc("test/process_open_files.arrow")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/aaron/.local/lib/python3.10/site-packages/polars/io/ipc/functions.py", line 102, in read_ipc
    return pl.DataFrame._read_ipc(
  File "/home/aaron/.local/lib/python3.10/site-packages/polars/dataframe/frame.py", line 982, in _read_ipc
    self._df = PyDataFrame.read_ipc(
exceptions.ArrowErrorException: OutOfSpec("InvalidFooter")

>>> # Just the same table again and it works.
>>> pl.read_ipc("test/process_open_files.arrow")
shape: (1_520, 3)
┌─────┬───────────────────────────────────┬───────┐
│ fd  ┆ path                              ┆ pid   │
│ --- ┆ ---                               ┆ ---   │
│ str ┆ str                               ┆ str   │
╞═════╪═══════════════════════════════════╪═══════╡
│ 0   ┆ /dev/null                         ┆ 14268 │
│ 107 ┆ /home/aaron/snap/firefox/common/… ┆ 14268 │
│ 108 ┆ /home/aaron/snap/firefox/common/… ┆ 14268 │
│ 109 ┆ /home/aaron/snap/firefox/common/… ┆ 14268 │
│ …   ┆ …                                 ┆ …     │
│ 255 ┆ /dev/pts/1                        ┆ 6818  │
│ 0   ┆ /dev/null                         ┆ 7420  │
│ 0   ┆ /dev/null                         ┆ 9555  │
│ 11  ┆ /run/user/1000/update-notifier.p… ┆ 9555  │
└─────┴───────────────────────────────────┴───────┘
>>>

```
