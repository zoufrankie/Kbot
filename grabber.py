import cv2
import numpy as np
import mss
import pyautogui
import time
import ctypes
import random
import threading
from pathlib import Path

# =========================================================================
# SETTINGS
# =========================================================================
TEST_CLICK_MODE = False # Set to True to test clicking reaction2 and 3 manually
TEST_MODE = False      # Set to True to wait 5 seconds instead of 9m 50s
MONITOR_INDEX = 1      # 1 = Primary Monitor (left). Change to 2 if needed.
TEXT_BOX_Y_OFFSET = 80 # Adjusts the height of the text boxes
# =========================================================================

def enable_dpi():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

def load_templates():
    downloads = Path.home() / "Downloads"
    script_dir = Path(__file__).parent
    templates = []
    
    for i in range(1, 4):
        filename = f"reaction{i}.png"
        path = downloads / filename
        if not path.exists():
            path = script_dir / filename
            
        if not path.exists():
            print(f"[ERROR] Could not find {filename} in Downloads or script directory.")
            return None
            
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            print(f"[ERROR] Could not load image: {path}")
            return None
        templates.append(img)
        
    return templates

def double_click(x, y):
    """Clicks 2 times at the given coordinates, waiting 1 second between each."""
    pyautogui.click(x, y)
    time.sleep(1)
    pyautogui.click(x, y)

def debug_overlay(stop_event, monitor, W_half, H_half, text_boxes):
    with mss.mss() as sct:
        cv2.namedWindow("Debug Overlay", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Debug Overlay", 1280, 720)

        while not stop_event.is_set():
            try:
                img = np.array(sct.grab(monitor))[:, :, :3]
                overlay = img.copy()

                cv2.line(overlay, (W_half, 0), (W_half, monitor["height"]), (0, 255, 0), 2)
                cv2.line(overlay, (0, H_half), (monitor["width"], H_half), (0, 255, 0), 2)

                for i, (tx, ty) in enumerate(text_boxes):
                    local_x = tx - monitor["left"]
                    local_y = ty - monitor["top"]
                    cv2.drawMarker(overlay, (local_x, local_y), (0, 0, 255), cv2.MARKER_CROSS, 40, 3)
                    cv2.putText(overlay, f"Box {i}", (local_x + 25, local_y - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                blended = cv2.addWeighted(overlay, 0.6, img, 0.4, 0)
                cv2.imshow("Debug Overlay", blended)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    stop_event.set()
                    break
                if cv2.getWindowProperty("Debug Overlay", cv2.WND_PROP_VISIBLE) < 1:
                    stop_event.set()
                    break
            except Exception as e:
                print(f"[Debug Overlay] Error: {e}")
                time.sleep(1)
            time.sleep(0.3)
        cv2.destroyAllWindows()

def main():
    enable_dpi()
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0

    templates = load_templates()
    if templates is None:
        return

    template_info = [(t.shape[1], t.shape[0]) for t in templates]
    print(f"Loaded {len(templates)} reaction templates successfully.")

    with mss.mss() as sct:
        try:
            monitor = sct.monitors[MONITOR_INDEX]
        except IndexError:
            print(f"Monitor index {MONITOR_INDEX} not found. Falling back to primary (1).")
            monitor = sct.monitors[1]

    W_half = monitor["width"] // 2
    H_half = monitor["height"] // 2

    window_offsets = [
        (monitor["left"], monitor["top"]),                           # Window 0
        (monitor["left"] + W_half, monitor["top"]),                  # Window 1
        (monitor["left"], monitor["top"] + H_half),                  # Window 2
        (monitor["left"] + W_half, monitor["top"] + H_half)          # Window 3
    ]

    TEXT_BOXES = [
        (monitor["left"] + (W_half // 2), monitor["top"] + H_half - TEXT_BOX_Y_OFFSET),                           
        (monitor["left"] + W_half + (W_half // 2), monitor["top"] + H_half - TEXT_BOX_Y_OFFSET),                  
        (monitor["left"] + (W_half // 2), monitor["top"] + monitor["height"] - TEXT_BOX_Y_OFFSET),                
        (monitor["left"] + W_half + (W_half // 2), monitor["top"] + monitor["height"] - TEXT_BOX_Y_OFFSET)        
    ]

    print("Starting Debug Overlay... (Press 'q' on the overlay to close it)")
    stop_event = threading.Event()
    overlay_thread = threading.Thread(
        target=debug_overlay,
        args=(stop_event, monitor, W_half, H_half, TEXT_BOXES),
        daemon=True
    )
    overlay_thread.start()

    if TEST_CLICK_MODE:
        print("\n=== TEST CLICK MODE ACTIVATED ===")
        print("Scanning for reaction2 and reaction3...")
        clicked_2 = False
        clicked_3 = False

        with mss.mss() as sct:
            while True:
                screen = np.array(sct.grab(monitor))[:, :, :3]
                
                if not clicked_2:
                    res2 = cv2.matchTemplate(screen, templates[1], cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res2)
                    if max_val >= 0.80:
                        mx, my = max_loc
                        tw, th = template_info[1]
                        print(f"[TEST] Found reaction2! Double-clicking...")
                        double_click(mx + tw // 2, my + th // 2)
                        clicked_2 = True
                        
                if not clicked_3:
                    res3 = cv2.matchTemplate(screen, templates[2], cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res3)
                    if max_val >= 0.80:
                        mx, my = max_loc
                        tw, th = template_info[2]
                        print(f"[TEST] Found reaction3! Double-clicking...")
                        double_click(mx + tw // 2, my + th // 2)
                        clicked_3 = True
                        
                if clicked_2 and clicked_3:
                    print("Both reactions tested! Restart the script to test again.")
                    clicked_2 = False
                    clicked_3 = False
                    
                time.sleep(0.1)

    turn = 0
    first_run = True
    
    with mss.mss() as sct:
        while True:
            try:
                print(f"\n--- TURN {turn} ---")
                print(f"This cycle, Window {turn} is the dropper.")
                
                if first_run:
                    wait_time = 5
                    print(f"First run detected! Waiting {wait_time} seconds for initial drop...")
                    first_run = False
                elif TEST_MODE:
                    wait_time = 5
                    print(f"TEST MODE: Waiting {wait_time} seconds...")
                else:
                    wait_time = random.uniform(590, 600)
                    print(f"Waiting {wait_time/60:.1f} minutes for next drop window...")
                time.sleep(wait_time)

                dropper = turn
                other_windows = [i for i in range(4) if i != dropper]
                grabbers = random.sample(other_windows, 2)
                targets = [dropper, grabbers[0], grabbers[1]]

                print(f"Window {dropper} (Dropper) -> Will grab reaction1")
                print(f"Window {grabbers[0]} -> Will grab reaction2")
                print(f"Window {grabbers[1]} -> Will grab reaction3")

                box = TEXT_BOXES[dropper]
                
                print(f"Clicking text box for Window {dropper}...")
                pyautogui.click(box[0], box[1])
                time.sleep(1)
                
                print("Typing k!d...")
                pyautogui.typewrite("k!d")
                time.sleep(1)
                
                print("Pressing Enter...")
                pyautogui.press("enter")
                
                print("Command sent! Waiting 5 seconds for cards to drop...")
                time.sleep(5.0) 

                # 4. Grab phase (Sequential and directly targets the correct window)
                for i in range(3):
                    target_win = targets[i]
                    card_found = False
                    grab_start = time.time()
                    timeout = 10.0 
                    
                    print(f"Looking for Card {i+1} in Window {target_win}...")
                    
                    while not card_found and (time.time() - grab_start) < timeout:
                        screen = np.array(sct.grab(monitor))[:, :, :3]
                        
                        ox, oy = window_offsets[target_win]
                        rel_ox = ox - monitor["left"]
                        rel_oy = oy - monitor["top"]
                        
                        quadrant = screen[rel_oy:rel_oy+H_half, rel_ox:rel_ox+W_half]
                        if quadrant.size == 0:
                            continue
                            
                        res = cv2.matchTemplate(quadrant, templates[i], cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        
                        if max_val >= 0.80:
                            # RE-CHECK JUST BEFORE GRABBING
                            time.sleep(0.1)
                            screen = np.array(sct.grab(monitor))[:, :, :3]
                            quadrant = screen[rel_oy:rel_oy+H_half, rel_ox:rel_ox+W_half]
                            res = cv2.matchTemplate(quadrant, templates[i], cv2.TM_CCOEFF_NORMED)
                            _, max_val, _, max_loc = cv2.minMaxLoc(res)
                            
                            if max_val >= 0.80:
                                target_x = ox + max_loc[0] + template_info[i][0] // 2
                                target_y = oy + max_loc[1] + template_info[i][1] // 2
                                
                                print(f"Found Card {i+1} in Window {target_win}! Double-clicking...")
                                double_click(target_x, target_y)
                                card_found = True
                                
                        time.sleep(0.1)
                        
                    if not card_found:
                        print(f"Timeout: Could not find Card {i+1} in Window {target_win}.")
                        break
                        
                    print(f"Card {i+1} claimed! Waiting 3 seconds for chat to shift...")
                    time.sleep(3.0)

                print("Finished grab sequence for this turn.")
                
                turn = (turn + 1) % 4

            except KeyboardInterrupt:
                print("\nBot stopped by user.")
                stop_event.set()
                break
            except Exception as e:
                print(f"Unexpected Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    main()