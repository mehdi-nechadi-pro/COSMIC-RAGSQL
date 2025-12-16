
#NAME, TYPE, CONSTELLATIONS, RA, DEC, MAGNITUDE, URL

# def get_wiki_image_safe(search_term):
#     try:
#         # On cherche la page précise "NGC 188"
#         page = wikipedia.page(search_term, auto_suggest=False)
        
#         # On prend la première image qui est un JPG et pas un Logo
#         for img in page.images:
#             if img.lower().endswith('.jpg') and "logo" not in img.lower():
#                 return img
#         return None
#     except:
#         return None


# print("📸 Début de la récupération des images NGC/IC...")

# results = {}

# for c_id, ngc_name in caldwell_ngc.items():
    
#     # On interroge Wikipédia avec le VRAI nom (NGC 188, pas C1)
#     image_url = get_wiki_image_safe(ngc_name)
    
#     if image_url:
#         print(f"✅ {c_id} ({ngc_name}) : Image trouvée !")
#         results[c_id] = image_url
#     else:
#         print(f"⚠️ {c_id} ({ngc_name}) : Pas d'image trouvée.")
#         results[c_id] = "PLACEHOLDER_URL" # Mettez une image par défaut
    
#     time.sleep(1) 

# print(results)
# final_data = {}

# for c_id, url_image in results.items():
    
#     # On récupère le nom scientifique (NGC/IC) depuis ton dictionnaire de départ
#     scientific_name = caldwell_ngc.get(c_id, "Inconnu")
    
#     # On crée la structure propre
#     final_data[c_id] = {
#         "scientific_name": scientific_name, # Ex: "NGC 188"
#         "image_url": url_image              # Ex: "https://..."
#     }

# # Sauvegarde dans le JSON
# with open("caldwell_data_complete.json", "w", encoding="utf-8") as f:
#     json.dump(final_data, f, indent=4, ensure_ascii=False)

# print("✅ Fichier 'caldwell_data_complete.json' généré ! Tu as tout dedans.")

#print("Base de données consolidée prête !")
