import os
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import argparse
import threading
from queue import Queue

class WebsiteCloner:
    def __init__(self, base_url, output_dir="cloned_site", max_threads=5):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.output_dir = output_dir
        self.visited_urls = set()
        self.queue = Queue()
        self.max_threads = max_threads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

        # Créer le répertoire de sortie
        os.makedirs(self.output_dir, exist_ok=True)

    def is_valid_url(self, url):
        """Vérifie si l'URL appartient au même domaine"""
        parsed = urlparse(url)
        return parsed.netloc == self.domain or not parsed.netloc

    def get_relative_path(self, url):
        """Convertit une URL en chemin relatif pour le stockage local"""
        parsed = urlparse(url)
        path = parsed.path.lstrip('/')
        
        if not path:
            path = 'index.html'
        elif '.' not in os.path.basename(path):
            path = os.path.join(path, 'index.html')
            
        return os.path.join(self.output_dir, path)

    def save_content(self, url, content):
        """Sauvegarde le contenu dans le système de fichiers"""
        path = self.get_relative_path(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        mode = 'wb' if isinstance(content, bytes) else 'w'
        with open(path, mode) as f:
            f.write(content)
        
        print(f"[+] Sauvegardé: {url} -> {path}")

    def download_asset(self, url):
        """Télécharge une ressource (image, CSS, JS, etc.)"""
        try:
            response = self.session.get(url, stream=True, timeout=10)
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'text' in content_type:
                    return response.text
                return response.content
        except Exception as e:
            print(f"[-] Erreur lors du téléchargement de {url}: {e}")
        return None

    def process_page(self, url):
        """Traite une page HTML, télécharge le contenu et trouve de nouveaux liens"""
        if url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        print(f"[*] Traitement de: {url}")
        
        content = self.download_asset(url)
        if not content:
            return
            
        # Sauvegarder la page originale
        self.save_content(url, content)
        
        if 'text/html' in self.session.head(url).headers.get('Content-Type', ''):
            soup = BeautifulSoup(content, 'html.parser')
            
            # Mettre à jour les liens dans la page
            for tag in soup.find_all(['a', 'link', 'script', 'img', 'source']):
                attr = 'href' if tag.name in ['a', 'link'] else 'src'
                if tag.has_attr(attr):
                    absolute_url = urljoin(url, tag[attr])
                    
                    # Ne traiter que les URLs du même domaine
                    if self.is_valid_url(absolute_url):
                        # Ajouter à la file d'attente si c'est une page HTML
                        if absolute_url not in self.visited_urls and urlparse(absolute_url).path.endswith(('.html', '.htm', '.php', '/', '')):
                            self.queue.put(absolute_url)
                        
                        # Télécharger les ressources
                        asset_content = self.download_asset(absolute_url)
                        if asset_content:
                            self.save_content(absolute_url, asset_content)
                            
                            # Mettre à jour le lien dans la page pour pointer vers la version locale
                            tag[attr] = os.path.relpath(
                                self.get_relative_path(absolute_url),
                                os.path.dirname(self.get_relative_path(url)))
            
            # Sauvegarder la page modifiée avec les liens locaux
            modified_path = self.get_relative_path(url)
            with open(modified_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))

    def worker(self):
        """Fonction exécutée par chaque thread"""
        while True:
            url = self.queue.get()
            try:
                self.process_page(url)
            except Exception as e:
                print(f"[-] Erreur avec {url}: {e}")
            finally:
                self.queue.task_done()

    def start_cloning(self):
        """Lance le processus de clonage"""
        self.queue.put(self.base_url)
        
        # Créer les threads workers
        for _ in range(self.max_threads):
            t = threading.Thread(target=self.worker, daemon=True)
            t.start()
        
        self.queue.join()
        print("\n[+] Clonage terminé!")

def main():
    parser = argparse.ArgumentParser(description="Outil de clonage de site web")
    parser.add_argument("url", help="URL du site à cloner")
    parser.add_argument("-o", "--output", help="Répertoire de sortie", default="cloned_site")
    parser.add_argument("-t", "--threads", help="Nombre de threads", type=int, default=5)
    
    args = parser.parse_args()
    
    cloner = WebsiteCloner(args.url, args.output, args.threads)
    cloner.start_cloning()

if __name__ == "__main__":
    main()
