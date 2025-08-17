import json
from datetime import datetime
import requests
import base64
import os

JSON_INPUT = 'miizy_dump.json'
JSON_OUTPUT = 'miizy_properties_structured.json'


def create_miizy_dump():
    # --- Configuration ---
    API_URL = 'https://miizy.com/miizy/stock'
    TOKEN = '13|ogjKAODJddAY1UT2eJxC6Mq6bzrGzahkWxv5K5jC'
    HEADERS = {'Authorization': f'Bearer {TOKEN}'}
    PARAMS = {
        'promoter_per_page': 200,
        'estates_per_promoter': 200
    }

    # --- Requête API ---
    response = requests.get(API_URL, headers=HEADERS, params=PARAMS)
    if response.status_code != 200:
        raise Exception(
            f"Erreur API : {response.status_code} - {response.text}")

    # --- Récupération JSON brut ---
    data = response.json()

    # --- Sauvegarde dans un fichier ---
    with open(JSON_INPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Données Miizy sauvegardées dans 'miizy_dump.json'")


def get_property_type(type_code):
    """Convertit le code type en description"""
    type_mapping = {
        0: "Maison",
        1: "Appartement",
    }
    return type_mapping.get(type_code, f"Type {type_code}" if type_code else "N/A")


def get_parking_info(prop):
    """Extrait les informations de parking"""
    parking = prop.get('parking')
    if parking is None or parking == 0:
        return "Non"
    elif parking == 1:
        return "Oui (1 place)"
    else:
        return f"Oui ({parking} places)"


def get_main_exterior(prop):
    """Détermine le type d'extérieur principal"""
    exteriors = []

    # Fonction helper pour convertir en float sécurisé
    def safe_float(value):
        try:
            return float(value) if value not in [None, '', 'N/A'] else 0
        except (ValueError, TypeError):
            return 0

    terrasse = safe_float(prop.get('terrasse', 0))
    if terrasse > 0:
        exteriors.append(("Terrasse", terrasse))

    balcon = safe_float(prop.get('balcon', 0))
    if balcon > 0:
        exteriors.append(("Balcon", balcon))

    balcon_2 = safe_float(prop.get('balcon_2', 0))
    if balcon_2 > 0:
        exteriors.append(("Balcon 2", balcon_2))

    jardin = safe_float(prop.get('jardin', 0))
    if jardin > 0:
        exteriors.append(("Jardin", jardin))

    loggia = safe_float(prop.get('loggia', 0))
    if loggia > 0:
        exteriors.append(("Loggia", loggia))

    if exteriors:
        # Trier par surface décroissante pour prendre le plus grand comme principal
        exteriors.sort(key=lambda x: x[1], reverse=True)
        main_type, main_surface = exteriors[0]
        return main_type, main_surface  # Retourner seulement le nom sans parenthèses
    else:
        return "Aucun", "N/A"


def get_exterior_surface(prop):
    """Calcule la surface totale extérieure"""

    # Fonction helper pour convertir en float sécurisé
    def safe_float(value):
        try:
            return float(value) if value not in [None, '', 'N/A'] else 0
        except (ValueError, TypeError):
            return 0

    total = 0
    surfaces = ['terrasse', 'balcon', 'balcon_2', 'jardin', 'loggia']

    for surface in surfaces:
        value = safe_float(prop.get(surface, 0))
        if value > 0:
            total += value

    return total if total > 0 else "N/A"


def extract_bedroom_count(prop):
    """Extrait le nombre de chambres"""
    rooms = prop.get('rooms')
    if not rooms or rooms <= 1:
        return 0
    elif rooms == 2:
        return 1  # T2 = généralement 1 chambre
    else:
        return rooms - 1  # T3 = 2 chambres, T4 = 3 chambres, etc.


def extract_bathroom_count(prop):
    """Extrait le nombre de salles de bain/WC"""
    rooms = prop.get('rooms', 0)

    # Estimation basée sur le nombre de pièces
    if rooms <= 1:
        return 1  # Studio/T1
    elif rooms <= 3:
        return 1  # T2/T3
    elif rooms <= 4:
        return 2  # T4
    else:
        return 2  # T5+


def analyze_miizy_dump():
    """Analyse le fichier miizy_dump.json et extrait les propriétés structurées"""

    print("🏠 ANALYSE DU FICHIER MIIZY_DUMP.JSON")
    print("=" * 50)

    print("📂 Chargement des données...")
    try:
        with open(JSON_INPUT, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(
            f"✅ Données chargées: {len(data['original']['data'])} promoteurs")
    except Exception as e:
        print(f"❌ Erreur lors du chargement du JSON: {e}")
        return None

    properties_list = []

    print("🔄 Extraction des propriétés...")

    for entry in data["original"]["data"]:
        promoter_data = entry.get("promoter", {})
        promoter_name = promoter_data.get('name', 'N/A')

        for stock in promoter_data.get("stock", []):
            # Informations du programme
            programme_name = stock.get('name', 'N/A')

            # Informations de localisation
            address_data = stock.get('address', {}) or {}
            city_data = stock.get('city', {}) or {}

            # Ville et code postal
            if isinstance(city_data, dict):
                ville = city_data.get('name', 'N/A')
                code_postal = city_data.get('postcode', 'N/A')
            else:
                ville = city_data if city_data else 'N/A'
                code_postal = 'N/A'

            # Adresse de publication
            number = address_data.get('number', '') or ''
            street = address_data.get('street', '') or ''
            adresse_publication = f"{number} {street}".strip()
            if not adresse_publication:
                adresse_publication = 'N/A'

            # Date de livraison
            deliv_year = stock.get('deliv_year', '')
            deliv_trimestre = stock.get('deliv_trimestre', '')
            if deliv_year and deliv_trimestre:
                date_livraison = f"T{deliv_trimestre} {deliv_year}"
            elif deliv_year:
                date_livraison = str(deliv_year)
            else:
                date_livraison = 'N/A'

            # Traitement de chaque bien individuel
            for prop in stock.get("properties", []):
                # Filtrage par fiscalité - ne garder que les fiscalités autorisées
                fiscality = prop.get('fiscality', '')
                allowed_fiscalities = ['Accession',
                                       'Déficit Foncier', 'Droit Commun']

                # Vérifier si la fiscalité est dans la liste autorisée
                if fiscality not in allowed_fiscalities:
                    continue  # Ignorer ce bien

                # Filtrage par status - ne garder que les biens avec status = 0
                status = prop.get('status', '')
                if status != 0:
                    continue  # Ignorer ce bien

                # Obtenir les informations sur l'extérieur principal
                main_exterior_info, main_exterior_surface = get_main_exterior(
                    prop)

                property_info = {
                    "Ville": ville,
                    "Code_Postal": code_postal,
                    "Adresse_de_publication": adresse_publication,
                    "Type": get_property_type(prop.get('type')),
                    "Typologie": f"{prop.get('rooms', 'N/A')} pièces" if prop.get('rooms') else 'N/A',
                    "Etage": prop.get('floor', 'N/A'),
                    "Metre": prop.get('surface', 'N/A'),
                    "Prix": prop.get('price', 'N/A'),
                    "VAT": prop.get('vat', 'N/A'),
                    "Parking": get_parking_info(prop),
                    "Cave": "Oui" if prop.get('cave') else "Non",
                    "Exterieur_principale": main_exterior_info,
                    "Surface_exterieur_1": main_exterior_surface,
                    "Chambre": extract_bedroom_count(prop),
                    "Nombre_SDB_WC": extract_bathroom_count(prop),
                    "Date_de_livraison": date_livraison,
                    "Promoteur": promoter_name,
                    "Programme": programme_name,

                    # Informations supplémentaires utiles
                    "Reference": prop.get('ref', 'N/A'),
                    "Fiscalite": fiscality,
                    "Status": prop.get('status', 'N/A')
                }

                properties_list.append(property_info)

    return properties_list


def save_structured_json(properties_list):
    """Sauvegarde les données dans un fichier JSON structuré"""

    output_data = {
        "metadata": {
            "extraction_date": datetime.now().isoformat(),
            "total_properties": len(properties_list),
            "description": "Données immobilières Miizy structurées par bien",
            "source": "miizy_dump.json"
        },
        "properties": properties_list
    }

    try:
        with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Fichier JSON structuré créé: {JSON_OUTPUT}")
        print(f"📊 {len(properties_list)} biens extraits")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        return False


def show_statistics(properties_list):
    """Affiche les statistiques des données extraites"""

    print("\n📈 STATISTIQUES:")
    print("=" * 30)

    # Par ville
    cities = {}
    promoters = {}
    types = {}
    price_ranges = {"0-200k": 0, "200k-400k": 0, "400k-600k": 0, "600k+": 0}

    for prop in properties_list:
        # Villes
        city = prop['Ville']
        cities[city] = cities.get(city, 0) + 1

        # Promoteurs
        promoter = prop['Promoteur']
        promoters[promoter] = promoters.get(promoter, 0) + 1

        # Types
        prop_type = prop['Type']
        types[prop_type] = types.get(prop_type, 0) + 1

        # Prix
        price = prop['Prix']
        if price != 'N/A' and isinstance(price, (int, float)):
            if price < 200000:
                price_ranges["0-200k"] += 1
            elif price < 400000:
                price_ranges["200k-400k"] += 1
            elif price < 600000:
                price_ranges["400k-600k"] += 1
            else:
                price_ranges["600k+"] += 1

    print(f"\n🏙️ Top 5 des villes:")
    for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"   - {city}: {count} biens")

    print(f"\n🏢 Top 5 des promoteurs:")
    for promoter, count in sorted(promoters.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"   - {promoter}: {count} biens")

    print(f"\n🏠 Répartition par type:")
    for prop_type, count in sorted(types.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {prop_type}: {count} biens")

    print(f"\n💰 Répartition par gamme de prix:")
    for price_range, count in price_ranges.items():
        if count > 0:
            print(f"   - {price_range}: {count} biens")

def push_file_to_github():
    # Configuration GitHub
    GITHUB_USERNAME = "danhab05"
    REPO_NAME = "MiizyApi"
    FILE_PATH = "miizy_properties_structured.json"
    BRANCH = "main"

    # Vous devez mettre votre token GitHub ici
    # Créez un token sur https://github.com/settings/tokens
    GITHUB_TOKEN = "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"  # Remplacez par votre token

    # Chemin du fichier local
    local_file_path = "miizy_properties_structured.json"

    if not os.path.exists(local_file_path):
        print(f"❌ Fichier {local_file_path} introuvable!")
        return False

    print(f"📁 Lecture du fichier {local_file_path}...")

    # Lire le fichier local
    with open(local_file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()

    # Encoder en base64
    content_encoded = base64.b64encode(
        file_content.encode('utf-8')).decode('utf-8')

    # URL de l'API GitHub
    api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/{FILE_PATH}"

    # Headers
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    print("🔍 Vérification si le fichier existe déjà sur GitHub...")

    # Vérifier si le fichier existe déjà pour récupérer son SHA
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        # Le fichier existe, récupérer son SHA
        existing_file = response.json()
        sha = existing_file['sha']
        print("✅ Fichier existant trouvé, mise à jour...")
    elif response.status_code == 404:
        # Le fichier n'existe pas
        sha = None
        print("📝 Nouveau fichier, création...")
    else:
        print(f"❌ Erreur lors de la vérification: {response.status_code}")
        print(response.text)
        return False

    # Préparer les données pour l'upload
    data = {
        "message": "Update miizy_properties_structured.json via Python script",
        "content": content_encoded,
        "branch": BRANCH
    }

    # Ajouter le SHA si le fichier existe déjà
    if sha:
        data["sha"] = sha

    print("🚀 Upload vers GitHub en cours...")

    # Faire la requête PUT pour créer/modifier le fichier
    response = requests.put(api_url, headers=headers, json=data)

    if response.status_code in [200, 201]:
        print("✅ Fichier uploadé avec succès sur GitHub!")
        print(
            f"🔗 URL: https://github.com/{GITHUB_USERNAME}/{REPO_NAME}/blob/{BRANCH}/{FILE_PATH}")
        print(
            f"🔗 Raw URL: https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/{BRANCH}/{FILE_PATH}")
        return True
    else:
        print(f"❌ Erreur lors de l'upload: {response.status_code}")
        print(response.text)
        return False



def main():
    create_miizy_dump()
    properties_list = analyze_miizy_dump()

    if properties_list:
        # Sauvegarde JSON
        if save_structured_json(properties_list):
            # Statistiques
            show_statistics(properties_list)

            print(f"\n🎉 Analyse terminée avec succès!")
            print(f"📄 Fichier créé:")
            print(f"   - {JSON_OUTPUT}")
            # Push vers GitHub
            if push_file_to_github():
                print("🎉 Fichier uploadé sur GitHub avec succès!")
            else:   
                print("💥 Échec de l'upload sur GitHub!")
                
        else:
            print("❌ Échec de la sauvegarde")
    else:
        print("❌ Aucune donnée extraite")


if __name__ == "__main__":
    main()
