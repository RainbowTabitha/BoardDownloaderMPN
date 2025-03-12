import customtkinter as ctk
import requests
import os
import tempfile
import subprocess
import shutil
import threading

from io import BytesIO
from PIL import Image
from ctk_components.ctk_components import *
from datetime import datetime
from tkinter import filedialog

if sys.platform == "win32":
    config_dir = os.path.join(os.getenv("LOCALAPPDATA"), "BoardDownloaderMPN")
elif sys.platform == "darwin":  # macOS
    config_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "BoardDownloaderMPN")
else:  # Linux and other UNIX-like systems
    config_dir = os.path.join(os.path.expanduser("~"), ".config", "BoardDownloaderMPN")


# Create a temp folder for images
TEMP_DIR = config_dir
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Scale app 2.5x with DPI awareness
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")
scaling_factor = 2
ctk.set_widget_scaling(scaling_factor)

# Create main app
app = ctk.CTk()
app.title("Board Browser")
app.maxsize(int(1290 * scaling_factor), int(650 * scaling_factor))
app.minsize(int(1290 * scaling_factor), int(650 * scaling_factor))

# Configure grid layout
app.grid_columnconfigure(0, weight=1)
app.grid_rowconfigure(1, weight=1)

# Search Bar Frame
search_frame = ctk.CTkFrame(app)
search_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=15)
search_frame.grid_columnconfigure(0, weight=1)

search_var = ctk.StringVar()
search_entry = ctk.CTkEntry(search_frame, textvariable=search_var, height=25 * scaling_factor, width=400 * scaling_factor, placeholder_text="Search for a project...")
search_entry.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

search_button = ctk.CTkButton(search_frame, text="Search", command=lambda: fetch_data(), height=25 * scaling_factor, width=100)
search_button.grid(row=0, column=1, padx=10, pady=10)

def get_latest_rom_download_link(project_id):
    """
    Fetches the latest ROM file's download link for a given project and allows the user to save it.
    
    :param project_id: The ID of the project.
    """
    try:
        # Get file list from the correct endpoint
        files_url = f"https://partyplannerapi.naylahanegan.com/project/{project_id}/files"
        response = requests.get(files_url)
        response.raise_for_status()
        
        data = response.json()

        # Extract versions list
        versions = data.get("versions", [])

        if not versions:
            print("No versions found for this project.")
            return None

        # Sort by release_date (newest first)
        versions.sort(key=lambda x: x.get('release_date', ''), reverse=True)

        # Get the latest version's details
        latest_version = versions[0]
        file_id = latest_version.get("file_id")
        file_name = latest_version.get("file_name", "ROM_File.json")  # Default name if missing

        if not file_id:
            print("File ID not found for the latest version.")
            return None

        # Construct new download URL format: "files/<file_id>/"
        download_link = f"https://partyplannerapi.naylahanegan.com/project/{project_id}/files/{file_id}"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=file_name,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            title="Save ROM File As"
        )

        if not file_path:
            print("Save operation cancelled.")
            return

        # Download and save the file
        try:
            response = requests.get(download_link, stream=True)
            response.raise_for_status()

            with open(file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)

            print(f"ROM successfully saved to {file_path}")

        except requests.RequestException as e:
            print(f"Error downloading ROM file: {e}")

    except requests.RequestException as e:
        print(f"Error fetching ROM file: {e}")
        return None

def patch_rom(project_id):
    try:
        # Define user config folder based on OS
        if sys.platform == "win32":
            config_dir = os.path.join(os.getenv("LOCALAPPDATA"), "BoardDownloaderMPN")
        elif sys.platform == "darwin":  # macOS
            config_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "BoardDownloaderMPN")
        else:  # Linux and other UNIX-like systems
            config_dir = os.path.join(os.path.expanduser("~"), ".config", "BoardDownloaderMPN")

        os.makedirs(config_dir, exist_ok=True)
        pp64_exe_path = os.path.join(config_dir, "partyplanner-cli.exe")

        # Fetch project details
        files_url = f"https://partyplannerapi.naylahanegan.com/project/{project_id}/files"
        response = requests.get(files_url)
        response.raise_for_status()

        data = response.json()
        versions = data.get("versions", [])
        if not versions:
            print("No versions found for this project.")
            return None

        # Sort by release date (newest first)
        versions.sort(key=lambda x: x.get('release_date', ''), reverse=True)
        latest_version = versions[0]
        file_id = latest_version.get("file_id")

        if not file_id:
            print("File ID not found for the latest version.")
            return None

        download_link = f"https://partyplannerapi.naylahanegan.com/project/{project_id}/files/{file_id}"
        pp64Link = "https://github.com/PartyPlanner64/PartyPlanner64/releases/download/v0.8.2/partyplanner64-cli-win.exe"

        # Check if PP64 CLI exists before downloading
        if not os.path.exists(pp64_exe_path):
            print("PP64 CLI not found. Downloading...")
            try:
                r2 = requests.get(pp64Link, allow_redirects=True)
                r2.raise_for_status()
                with open(pp64_exe_path, 'wb') as f:
                    f.write(r2.content)
                print("PP64 CLI downloaded successfully.")
            except requests.RequestException as e:
                print(f"Error downloading PP64 CLI: {e}")
                sys.exit(1)

        # Get the actual download URL from the project JSON
        print("Fetching project file URL...")
        try:
            project_info = requests.get(download_link).json()
            file_url = project_info.get("download_link")
            if not file_url:
                print("Error: No valid download URL found in project data.")
                sys.exit(1)
        except requests.RequestException as e:
            print(f"Error fetching project info: {e}")
            sys.exit(1)

        # Download the project file
        print("Downloading project file...")
        try:
            r1 = requests.get(file_url, allow_redirects=True)
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(r1.content)
                temp_file_path = temp_file.name
            print("Project file downloaded successfully.")
        except requests.RequestException as e:
            print(f"Error downloading project file: {e}")
            sys.exit(1)

        # Ask user to select the ROM file
        rom_file_path = filedialog.askopenfilename(
            title="Select the ROM file for the Patch",
            filetypes=[("Nintendo 64 ROM", "*.z64")]
        )

        if not rom_file_path:
            print("No ROM file selected. Exiting.")
            sys.exit(1)

        print(f"Selected ROM file: {rom_file_path}")

        # Patch the game
        try:
            if sys.platform != 'win32':
                subprocess.run(["wine", pp64_exe_path, "overwrite", "--rom-file", rom_file_path, "--target-board-index", "0", "--board-file", temp_file_path, "--output-file", "tmp.z64"])
            else:
                subprocess.run([pp64_exe_path, "overwrite", "--rom-file", rom_file_path, "--target-board-index", "0", "--board-file", temp_file_path, "--output-file", "tmp.z64"])
            print("Patching completed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error during patching: {e}")
            sys.exit(1)

        # Ask user where to save the patched ROM
        output_rom_path = filedialog.asksaveasfilename(
            title="Select the Output ROM Location",
            filetypes=[("Patched ROM", "*.z64")],
            defaultextension=".z64"
        )

        if not output_rom_path:
            print("No output file selected. Exiting.")
            sys.exit(1)

        print(f"Output ROM will be saved to: {output_rom_path}")

        # Copy temporary patched ROM to the selected location
        shutil.copy("tmp.z64", output_rom_path)
        print("Patched ROM saved successfully.")

        # Cleanup temporary files
        os.remove(temp_file_path)

    except requests.RequestException as e:
        print(f"Error fetching ROM file: {e}")
        return None
        
def format_date(date_str):
    """Convert date from 'YYYY-MM-DD' to 'Month Day, Year' format."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%B %d, %Y")  # Example: March 11, 2025
    return formatted_date

def show_project_modal(details, project_id):
    """Create and display a modal window with project details in a side-by-side layout."""
    modal = ctk.CTkToplevel()
    modal.title(details['name'])
    modal.geometry("2200x1400")  # Adjusted for wider view
    modal.resizable(False, False)

    # Main content frame (split into two sections)
    content_frame = ctk.CTkFrame(modal)
    content_frame.pack(fill="both", expand=True, padx=20, pady=20)

    # Left side (Image + Description)
    left_frame = ctk.CTkFrame(content_frame)
    left_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")

    if details['image_path']:
        img = Image.open(details['image_path'])
        img.thumbnail((500, 500), Image.LANCZOS)  # Larger image
        img = ctk.CTkImage(light_image=img, size=(500, 200))
        image_label = ctk.CTkLabel(left_frame, image=img, text="")
        image_label.pack()

    description_label = ctk.CTkLabel(left_frame, text="Description", font=("Arial", 18, "bold"))
    description_label.pack(pady=(10, 5))

    description_text = ctk.CTkTextbox(left_frame, wrap="word", height=320, font=("Arial", 16))
    description_text.insert("1.0", details.get('description', "No description available"))
    description_text.configure(state="disabled")  # Read-only
    description_text.pack(fill="both", expand=True, padx=10)

    # Right side (Project Info)
    right_frame = ctk.CTkFrame(content_frame)
    right_frame.grid(row=0, column=1, padx=20, pady=10, sticky="nsew")

    labels = [
        f"Created on: {details.get('creation_date', 'Unknown')}",
        f"Difficulty: {'★' * details.get('difficulty', 1) + '☆' * (5 - details.get('difficulty', 1))}",
        f"Recommended Turns: {details.get('recommended_turns', 'N/A')}",
        f"Custom Events: {'Yes' if details.get('custom_events', 0) else 'No'}",
        f"Custom Music: {'Yes' if details.get('custom_music', 0) else 'No'}"
    ]

    for text in labels:
        label = ctk.CTkLabel(right_frame, text=text, font=("Arial", 20))
        label.pack(pady=5, anchor="w")

    # Buttons (Patch ROM & Download)
    button_frame = ctk.CTkFrame(right_frame)
    button_frame.pack(fill="x", pady=20)

    patch_button = ctk.CTkButton(button_frame, text="Patch ROM", height=50, width=200, font=("Arial", 20), command=lambda: patch_rom(project_id))
    patch_button.pack(side="left", padx=10)

    download_button = ctk.CTkButton(button_frame, text="Download", height=50, width=200, font=("Arial", 20), command=lambda: get_latest_rom_download_link(project_id))
    download_button.pack(side="right", padx=10)

    modal.mainloop()

def truncate_description(text, word_limit=12):
    """Limit description to a set number of words."""
    words = text.split()
    return " ".join(words[:word_limit]) + ("..." if len(words) > word_limit else "")

def download_image(image_url, project_id):
    """Download and save image locally."""
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content))

        # Resize image (50% smaller than original)
        img.thumbnail((125, 125), Image.LANCZOS)

        # Save locally
        file_path = os.path.join(TEMP_DIR, f"project_{project_id}.png")
        img.save(file_path)
        return file_path
    except Exception as e:
        print(f"Failed to load image: {e}")
        return None

def fetch_project_details(project_id):
    """Fetch project details, including description and icon."""
    url = f"https://partyplannerapi.naylahanegan.com/project/{project_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        image_path = None
        image_url = data.get("icon", None)

        if image_url:
            image_path = download_image(image_url, project_id)

        return {
            "name": data.get("name", ""),
            "author": data.get("author", ""),
            "creation_date": format_date(data.get('creation_date', 'Unknown')),
            "difficulty": data.get("difficulty", ""),
            "recommended_turns": data.get("recommended_turns", ""),
            "custom_events": data.get("customEvents", False),
            "custom_music": data.get("customMusic", False),
            "description": data.get("description", "No description available"),
            "image_path": image_path
        }

    except requests.RequestException:
        return None

# Scrollable Frame for Cards
main_frame = ctk.CTkFrame(app)
main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)

canvas = ctk.CTkCanvas(main_frame, highlightthickness=0, bg="#2b2b2b")
scrollbar = ctk.CTkScrollbar(main_frame, orientation="vertical", command=canvas.yview)
scrollable_frame = ctk.CTkFrame(canvas)

scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")

def on_mouse_scroll(event):
    """Enable mouse wheel scrolling."""
    canvas.yview_scroll(-1 * (event.delta // 120), "units")

canvas.bind_all("<MouseWheel>", on_mouse_scroll)

def update_card(project_id, project_name, card):
    """Fetch project details in a separate thread and update the card."""
    details = fetch_project_details(project_id)
    if details:
        card.card_1(
            width=300 * scaling_factor,
            height=250 * scaling_factor,
            title=f"{project_name}: by {details.get('author', '')}",
            text=truncate_description(details.get("description", "No description available")),
            button_text="More Info",
            command=lambda: threading.Thread(target=show_project_modal, args=(details, project_id), daemon=True).start(),
            image_path=details["image_path"],
        )
        
def fetch_data():
    """Fetch search results and update cards dynamically."""
    search_term = search_var.get().strip()
    if not search_term:
        return

    url = f"https://partyplannerapi.naylahanegan.com/project/search?searchTerm={search_term}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        results = response.json()

        # Clear existing widgets in scrollable_frame
        for widget in scrollable_frame.winfo_children():
            widget.destroy()

        # Create new cards dynamically (2 per row, stack below)
        for i, project in enumerate(results):  
            project_name = project.get("name")
            project_id = project.get("projectId")

            row, col = divmod(i, 2)  # 2 cards per row

            # Placeholder card
            card = CTkCard(master=scrollable_frame, border_width=1, corner_radius=5)
            card.card_1(width=300 * scaling_factor, height=250 * scaling_factor, 
                        title=project_name, text="Fetching details...",
                        button_text="Loading...", command=lambda: None)
            card.grid(row=row, column=col, padx=10, pady=20)

            # Run fetching in a separate thread to avoid freezing the UI
            threading.Thread(target=update_card, args=(project_id, project_name, card), daemon=True).start()

    except requests.RequestException:
        print("Error fetching search results")

app.mainloop()
