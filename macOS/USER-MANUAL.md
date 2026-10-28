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
    brew install dotnet openal-soft
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

The menu is a Mac app with its own window. It looks and works like the Open Rails menu on Windows.

1. Open the unzipped folder and **double-click `Open Rails`** (the app with the green logo).
    The menu window opens. *(If macOS refuses to open it, see "Troubleshooting".)*
    The first time, if the app cannot find the game, it asks you to choose the folder you
    unzipped; it remembers your choice.

    *Alternative:* **`Open Rails Menu.command`** opens the same menu in your web browser instead.
    Use it if the app does not start.
2. **Check the big white panel on the right.** If something is missing (for example the .NET
    runtime or your content), it shows a red **Setup problem** with how to fix it.
3. **Choose what to play:**

    | Field | What it does |
    |---|---|
    | **Installation profile** | A folder of content (see section 3). Most people have just one. |
    | **Route** | The route (the track and scenery). |
    | **Activity** | **- Explore Route -** is free driving. The other entries are prepared activities with tasks and a timetable. |
    | **Locomotive** | Explore: choose a locomotive to list only the trains that use it, or leave **- Any Locomotive -**. |
    | **Consist** | Explore: the train (locomotive and cars). |
    | **Starting at / Heading to** | Explore: where the train starts and where its path goes. |
    | **Time / Season / Weather** | Explore: the time of day (type it as `10:30`) and the conditions. For an activity these show the activity's own values, greyed out. |
    | **Duration / Difficulty** | Shown for an activity, greyed out. |

    The white panel shows details about your choice (the route, the locomotive, the path or the
    activity and its briefing). Press the small arrow on a section to read all of it.
4. Press **Start** (in the **Singleplayer** box). A game window opens. Loading a big route can take
    from a few seconds to several minutes. Please be patient.
5. The game runs on its own: you can close the menu window while you play. To play something
    else, close the game first, then use the menu again. (If you used `Open Rails Menu.command`,
    close its Terminal window to quit the menu.)

The menu remembers your last choices.

### The buttons at the bottom

| Button | What it does |
|---|---|
| **Content** | Shows your installation profiles and lets you add another content folder (it must contain `ROUTES`). |
| **Options** | Display options (see below). |
| **Tools** | **Show the log file** (`OpenRailsLog.txt` on your Desktop) and **Edit OpenRails.ini**. |
| **Documents** | This manual, and the Open Rails manual on the web. |
| **Logging** | Turns the log file on or off. Keep it on, it helps when something goes wrong. |

**Timetable** mode, **Resume/Replay** and **Multiplayer** are shown, greyed out, like in the
Windows menu. They are not available on macOS yet.

### If your content is not found

Press **Content**, type the folder that contains `ROUTES`, and press **Add**. The menu remembers it.

### Display options

Press **Options** in the menu. They are saved when you press **OK**.

| Option | What it does |
|---|---|
| **Full screen** | Plays full screen. Turn it off to play in a window. |
| **Show the whole 2D cab** | Older cabs are a 4:3 picture. On a widescreen display the top and bottom can be cut off. Turn this on to see the whole cab, with black bars at the sides. |
| **Viewing distance** | How far away scenery is drawn. **A shorter distance usually gives a smoother frame rate** (see "Smoother frame rate" below). |
| **Window size** | The size of the window when Full screen is off, for example `1280x720`. |

### Smoother frame rate

If the game becomes choppy, especially when you look back along a long train, lower the
**Viewing distance** in **Options** (for example to **Balanced: 1000 m** or **Fast: 750 m**).

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
| **"Failed to load library: libSDL2-2.0.0.dylib"** | You are using an older build that depended on a Homebrew library. Download the latest zip from the Releases page: it includes SDL2. |
| **Black screen, or "Loading.mgfx is missing"** | You are using a build made from the source code. Use the zip from the Releases page (section 2). |
| **macOS says the app or file "cannot be opened" or is from an unidentified developer** | Run the `xattr -dr com.apple.quarantine .` command from section 2, step 3. Or open **System Settings**, **Privacy & Security**, scroll down, and press **Open Anyway** next to the blocked app. |
| **"Python 3 was not found" (the app or the .command file says so)** | In Terminal run `xcode-select --install`, then try again. (Homebrew installs this normally.) |
| **The menu shows a red "Setup problem" about the .NET runtime** | In Terminal run `brew install dotnet`. |
| **The route list is empty** | The menu cannot find your content. See section 3, or press **Content** in the menu and add the folder. |
| **The frame rate drops, or the game feels slow (for example when looking back)** | Lower the **Viewing distance** in **Options** (section 4, "Smoother frame rate"). |
| **The cab is cut off** | Turn on **Show the whole 2D cab** in **Options** (section 4). |
| **The game does not open, or stops with an error** | The menu shows a message with the error code. The detailed log is the file **`OpenRailsLog.txt` on your Desktop** (menu: **Tools**, **Show the log file**). See "Getting help". |
| **F2 (save) does nothing** | On a Mac keyboard hold **fn** and press **F2** (section 5). |
| **The game crashed when saving** | Update to the latest release (section 6). Older builds had this bug. |
| **Loading is slow** | Big routes take a while. Wait for it. |

---

## 8. What is not included

- The Windows **Menu.exe** is not available on macOS. This menu replaces the most important part
  of it, with the same layout: choosing a route and starting an Explore or Activity run, plus a few display options.
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
