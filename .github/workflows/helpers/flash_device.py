import subprocess
import os

def flash_device():
    # Get the project directory from the environment variable
    project_dir = os.getenv("PROJECT_DIR", "")
    if not project_dir:
        raise ValueError("PROJECT_DIR environment variable is not set.")

    elf_file = os.path.join(project_dir, "build/Debug/CICD-HIL-AI.elf")
    if not os.path.isfile(elf_file):
        raise FileNotFoundError(f"ELF file not found: {elf_file}")

    # Define the command to flash the device
    command = [
        "STM32_Programmer_CLI",
        "-c", "port=SWD",
        "-w", os.path.join(project_dir, "build/Debug/CICD-HIL-AI.elf"),
        "-v",
        "-rst",
        "-run"
    ]

    try:
        # Run the command
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Flashing successful:")
        print(result.stdout.decode())
    except subprocess.CalledProcessError as e:
        print("Error during flashing:")
        print(e.stderr.decode())
        raise

if __name__ == "__main__":
    flash_device()