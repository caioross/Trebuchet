import os
import sys
import subprocess
import platform
import shutil

MODEL_FILENAME = "Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf"

def print_step(msg):
    print(f"\n{'='*50}\n🚀 {msg}\n{'='*50}")

def get_venv_executable(name):
    if platform.system() == "Windows":
        return os.path.join("venv", "Scripts", f"{name}.exe")
    return os.path.join("venv", "bin", name)

def has_nvidia_gpu():
    try:
        subprocess.check_output('nvidia-smi', shell=True)
        return True
    except:
        return False

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    os.chdir(project_root)

    print_step("CONFIGURANDO TREBUCHET v4.0 (OFFLINE BUNDLE)")

    model_path = os.path.join("models", MODEL_FILENAME)
    if os.path.exists(model_path):
        print(f"Modelo encontrado localmente: {MODEL_FILENAME}")
    else:
        print(f"AVISO: O modelo não está na pasta 'models'. O Trebuchet tentará baixar ao iniciar.")

    if not os.path.exists("venv"):
        print("⚙️ Criando ambiente virtual...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    
    pip_exe = get_venv_executable("pip")
    
    print("Instalando/Verificando bibliotecas...")
    subprocess.run([pip_exe, "install", "--upgrade", "pip"], check=True)

    if has_nvidia_gpu():
        print("GPU NVIDIA Detectada! Ativando aceleração...")
        env = os.environ.copy()
        env["CMAKE_ARGS"] = "-DLLAMA_CUBLAS=on"
        subprocess.run(
            [pip_exe, "install", "llama-cpp-python", "--upgrade", "--force-reinstall", "--no-cache-dir"],
            env=env, check=True
        )
    else:
        subprocess.run([pip_exe, "install", "llama-cpp-python"], check=True)

    subprocess.run([pip_exe, "install", "-r", "requirements.txt"], check=True)

    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write("GITHUB_TOKEN=\nNOTION_TOKEN=\n")

    print_step("CONFIGURAÇÃO FINALIZADA!")

if __name__ == "__main__":
    main()