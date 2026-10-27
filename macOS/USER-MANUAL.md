# Open Rails for macOS: User Manual

This is a **native macOS (Apple Silicon) build of the [Open Rails](http://www.openrails.org/)
train simulator**. It runs directly on your Mac, with no Windows, Wine or virtual machine.

> **Unofficial.** This is a community port made by Aman Prajapati. It is not made, supported or
> endorsed by the Open Rails team. Please do not ask them for help with this build; use the
> [issue tracker](https://github.com/Aman1945/OPEN-RAIL-MAC/issues) instead (see "Getting help").

---

## 1. What you need

| You need | Notes |
|---|---|
| A **Mac with Apple Silicon** (M1 or newer) | Intel Macs have not been tested. |
| **Homebrew** | Free package installer for Mac. Get it at [brew.sh](https://brew.sh). |
| **Route and train content** | This download does not include any routes or trains. You need MSTS or Open Rails content (see section 3). |
| Some free disk space | The program itself is about 120 MB. .NET and your routes need more. |

---

## 2. Install (once)

1. **Download** `OpenRails-macOS-arm64.zip` from the
    [latest release](https://github.com/Aman1945/OPEN-RAIL-MAC/releases/latest) and unzip it
    (double-click it in Finder). Use this download, **not** the green "Code" button on GitHub: the
    source code does not contain the compiled game or its shaders, and you would get a black screen.
2. Open **Terminal** (press Cmd + Space, type `Terminal`, press Enter) and install the
    prerequisites:
    ```bash
    brew install dotnet sdl2 openal-soft
    ```
3. Tell macOS that the downloaded files are safe to run. In Terminal, replace the folder name if
    you unzipped somewhere else:
    ```bash
    cd ~/Downloads/OpenRails-macOS-arm64
    xattr -dr com.apple.quarantine .
    ```

You only do this once.

---

## 3. Put your content in place

Open Rails needs MSTS or Open Rails content: a folder that contains `ROUTES`, `TRAINS` and
`GLOBAL`. Put it in a folder called **`MSTS`** in your home folder:

```
~/MSTS/
    ROUTES/    (one folder per route)
    TRAINS/    (CONSISTS, TRAINSET)
    GLOBAL/
    SOUND/
```

The menu also looks in `~/Documents/MSTS`, `~/Open Rails`, `~/Documents/Open Rails`,
`~/Games/MSTS` and `/Users/Shared/MSTS`. If your content is somewhere else, you can tell the menu
where (see section 4).

Folder names can be upper or lower case; the menu copes with both.

---

## 4. Start the game

1. Open the unzipped folder and **double-click `Open Rails Menu.command`**.
    A Terminal window opens, and then the menu opens in your web browser.
    *(If macOS refuses to open it, see "Troubleshooting".)*
2. **Look at the top of the menu.** It says **Setup OK**, or it lists what is missing and how to fix it.
3. **Choose what to play:**

    | Field | What it does |
    |---|---|
    | **Route** | The route (the track and scenery). |
    | **Mode: Explore** | Free driving. You choose the train, where it starts, and the weather. |
    | **Mode: Activity** | A prepared scenario with a timetable and tasks. Choose the activity. |
    | **Consist (train)** | Explore mode: the locomotive and cars. |
    | **Path** | Explore mode: where the train starts and which way it goes. |
    | **Time / Season / Weather** | Explore mode: time of day, and the conditions. |

4. Press **START**. A game window opens. Loading a big route can take from a few seconds to
    several minutes. Please be patient.
5. **Leave the Terminal window open while you play.** Closing it can also close the game.
    When you are finished, close the game, then close the Terminal window (or press Ctrl + C in it).

### If your content is not in the list of folders above

Open **Route content folder** in the menu, type the folder that contains `ROUTES`, and press
**Use**. The menu remembers it.

### Display options

Open **Display options** in the menu. They are saved when you press START.

| Option | What it does |
|---|---|
| **Full screen** | Plays full screen. Turn it off to play in a window. |
| **Show the whole 2D cab** | Older cabs are a 4:3 picture. On a widescreen display the top and bottom can be cut off. Turn this on to see the whole cab, with black bars at the sides. |
| **Viewing distance** | How far away scenery is drawn. **A shorter distance usually gives a smoother frame rate** (see "Smoother frame rate" below). |
| **Window size** | The size of the window when Full screen is off, for example `1280x720`. |

### Smoother frame rate

If the game becomes choppy, especially when you look back along a long train, lower the
**Viewing distance** in Display options (for example to **Balanced: 1000 m** or **Fast: 750 m**).

Why it helps: on a big route the game draws tens of thousands of objects every frame, and the
number grows with the viewing distance. In a test on the KonkanIR route, a viewing distance of
2000 m drew about 34,000 objects per frame at the start, 1500 m about 28,000, 1000 m about 18,000
and 750 m about 12,000. Fewer objects means less work per frame. How much smoother it gets depends
on your Mac and the route. In the game, **Alt + F5** (on a Mac keyboard: **fn + Option + F5**) shows the
information window with the frame rate.

### Starting from the command line instead

If you prefer Terminal, from the unzipped folder:

```bash
./run-openrails.sh -start -explorer "/path/to/ROUTES/Route/PATHS/file.pat" "/path/to/TRAINS/CONSISTS/train.con" 12:00:00 1 0
```

The last three values are the time, the season (0 spring, 1 summer, 2 autumn, 3 winter) and the
weather (0 clear, 1 snow, 2 rain).

---

## 5. Driving

These are the default keys, the same as in the Windows version. **Press F1 in the game to see the
full list.**

| Action | Key |
|---|---|
| Throttle up / down | **D** / **A** |
| Direction forward / reverse | **W** / **S** |
| Train brake apply / release | **'** (apostrophe) / **;** (semicolon) |
| Locomotive brake apply / release | **]** / **[** |
| Emergency brake | **Backspace** |
| Horn | **Space** |
| Bell | **B** |
| Headlight | **L** |
| Wipers | **V** |
| Throw the switch ahead / behind | **G** / **Shift + G** |
| Cab view | **1** |
| Outside views: front / rear / trackside | **2** / **3** / **4** |
| Passenger view / brakeman view / free camera | **5** / **6** / **8** |
| Look around | **Arrow keys** |
| Zoom (outside views) | **Page Up** / **Page Down** |
| Track monitor / switch window / next station | **F4** / **F8** / **F10** |
| **Pause menu** (resume or quit) | **Esc** |
| **Save the game** | **F2** |

**Mac keyboards:** the F-keys usually need the **fn** key (hold **fn** and press **F2**), unless you
have turned on "Use F1, F2, etc. keys as standard function keys" in System Settings, Keyboard.

If the game starts with a menu showing, press **Esc** to carry on.

---

## 6. Updating to a new version

Download the new zip from the [releases page](https://github.com/Aman1945/OPEN-RAIL-MAC/releases/latest),
unzip it, and repeat step 3 of section 2 (`xattr ...`). Your content stays where it is.

If you changed settings in `Program/OpenRails.ini`, copy that file from the old folder into the
new `Program` folder, because the new zip contains a fresh one.

---

## 7. Troubleshooting

| Problem | What to do |
|---|---|
| **Black screen, or "Loading.mgfx is missing"** | You are using a build made from the source code. Use the zip from the Releases page (section 2). |
| **macOS says the file "cannot be opened" or is from an unidentified developer** | Run the `xattr -dr com.apple.quarantine .` command from section 2, step 3. Or open **System Settings**, **Privacy & Security**, scroll down, and press **Open Anyway** next to the blocked file. |
| **"Python 3 was not found"** | In Terminal run `xcode-select --install`, then try again. (Homebrew installs this normally.) |
| **Menu says ".NET runtime" is missing** | In Terminal run `brew install dotnet`. |
| **The route list is empty** | The menu cannot find your content. See section 3, or use **Route content folder** in the menu. |
| **The frame rate drops, or the game feels slow (for example when looking back)** | Lower the **Viewing distance** in Display options (section 4, "Smoother frame rate"). |
| **The cab is cut off** | Turn on **Show the whole 2D cab** in Display options (section 4). |
| **The game does not open, or stops with an error** | The menu shows a message with the error code. The detailed log is the file **`OpenRailsLog.txt` on your Desktop**. See "Getting help". |
| **F2 (save) does nothing** | On a Mac keyboard hold **fn** and press **F2** (section 5). |
| **The game crashed when saving** | Update to the latest release (section 6). Older builds had this bug. |
| **Loading is slow** | Big routes take a while. Wait for it. |

---

## 8. What is not included

- The Windows **Menu.exe** is not available on macOS. This menu replaces the most important part
  of it: choosing a route and starting an Explore or Activity run, plus three display options.
- **Timetable mode, multiplayer, and the content installer/updater** are not in the menu, and have
  not been tested on macOS.
- Loading a **saved game** is not offered by the menu yet.
- Other settings from the Windows Options window can still be changed by editing
  `Program/OpenRails.ini`.
- RailDriver hardware is not supported.
- Built and tested for **Apple Silicon** only. Intel Macs have not been tested.

---

## 9. Getting help

Open an issue at **<https://github.com/Aman1945/OPEN-RAIL-MAC/issues>** and tell me:

1. What you did and what happened.
2. Your Mac model and macOS version.
3. The file **`OpenRailsLog.txt`** from your Desktop (drag it into the issue).

---

## 10. Credits and license

- **Open Rails** is created by the Open Rails team and its contributors:
  [openrails.org](http://www.openrails.org/).
- **macOS / Apple Silicon port:** Aman Prajapati (India).
- Open Rails is released under the **GNU General Public License (GPL)**, and so is this port.
  The source code is in this repository.
