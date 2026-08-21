# 1. Utiliser une image Python officielle légère
FROM python:3.12-slim

# 2. Empêcher Python de créer des fichiers .pyc et forcer l'affichage immédiat des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Définir le dossier de travail dans le conteneur
WORKDIR /app

# 4. Copier les dépendances et les installer
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copier le reste du code source
COPY . .

# 6. Exposer le port sur lequel Uvicorn écoute
EXPOSE 8000

# 7. Commande par défaut pour démarrer le serveur
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]