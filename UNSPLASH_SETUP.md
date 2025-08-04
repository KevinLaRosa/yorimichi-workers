# Configuration Unsplash pour images gratuites

## 🎯 Obtenir une clé API Unsplash (GRATUIT)

1. **Créer un compte** : https://unsplash.com/join
2. **Aller sur** : https://unsplash.com/developers
3. **Cliquer** : "Your apps" → "New Application"
4. **Accepter** les conditions
5. **Nom de l'app** : "Yorimichi Tourism"
6. **Description** : "Finding beautiful images for Tokyo tourist spots"

## 📋 Récupérer la clé

Dans votre app Unsplash :
- **Access Key** : C'est votre clé API
- **Secret Key** : Pas nécessaire pour les recherches

## 🔧 Configuration

Ajouter dans `.env.local` :
```
UNSPLASH_ACCESS_KEY=votre_access_key_ici
```

## 📊 Limites gratuites

- **5,000 requêtes par heure** ✅
- **Pas de carte bancaire requise** ✅
- **Images haute qualité** ✅
- **Usage commercial autorisé** ✅

## 🎨 Avantages

- Images professionnelles de Tokyo
- Toujours à jour
- Légal et gratuit
- Qualité garantie

## ⚠️ Si pas de clé Unsplash

Le crawler fonctionnera quand même, mais sans images automatiques.