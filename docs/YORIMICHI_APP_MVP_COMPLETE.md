# 🚀 YORIMICHI - Guide Complet de Développement MVP

_Version 1.0 - Décembre 2024_

---

## 📱 Vue d'Ensemble du Projet

### Identité & Positionnement
- **Nom**: Yorimichi (寄り道 - "faire un détour")
- **Titre App Store**: `Yorimichi: Tokyo Offline Map`
- **Sous-titre**: `Your AI Expert Guide`
- **Vision**: Le guide de voyage le plus "lovely", personnel et intelligent pour Tokyo

### Modèle Économique
- **Modèle**: Freemium avec achat unique Pro
- **Prix**: 19,99€ (offre de lancement: 14,99€)
- **Version Gratuite**: Quartier Shibuya + 3 questions IA/jour
- **Version Pro**: Tous les quartiers + IA illimitée + cartes offline

---

## 🛠 Stack Technique Complète

### Framework & Core
```json
{
  "framework": "Expo SDK 50",
  "language": "TypeScript 5.3",
  "platform": "React Native 0.73",
  "architecture": "Clean Architecture"
}
```

### Librairies Principales
- **Navigation**: React Navigation 6 (Stack + Tab)
- **Styling**: Unistyles (performance optimale)
- **Animations**: React Native Reanimated 3
- **Graphismes**: Shopify Skia
- **Base de données**: WatermelonDB
- **Cartes**: react-native-maps (Mapbox)
- **Paiements**: RevenueCat
- **État global**: Zustand

### Services Backend
- **API**: Supabase (PostgreSQL + Edge Functions)
- **IA**: RAG Agent (Edge Function)
- **Sync**: Real-time + offline-first
- **Analytics**: PostHog / Mixpanel

---

## 🎨 Design System "Tokyo Metro"

### Palette de Couleurs
```typescript
const metroPalette = {
  // Base
  white: '#FFFFFF',
  lightGrey: '#F5F5F7',
  mediumGrey: '#A9A9A9',
  darkGrey: '#424242',
  black: '#1C1C1E',
  
  // Lignes de métro
  ginzaOrange: '#FF9500',
  marunouchiRed: '#F62E36',
  hibiyaSilver: '#B5B5B5',
  chiyodaGreen: '#00BB85',
  tozaiBlue: '#009BBF',
  hanzomonPurple: '#8F76D6',
  nambokuEmerald: '#00AC9B',
  yurakuchoGold: '#C1A470',
  fukutoshinBrown: '#9C6628'
}
```

### Typographie
- **Police**: Manrope (Google Fonts)
- **Poids**: Regular 400, Medium 500, Bold 700
- **Hiérarchie**: h1 (32px), h2 (24px), body (16px), caption (12px)

### Composants UI
- Boutons avec feedback haptique
- Cards avec animations spring
- Bottom sheets gestuels
- Progress bars animées
- Badges et chips colorés

---

## 🗺 Architecture de l'Application

### Structure des Dossiers
```
yorimichi-app/
├── src/
│   ├── domain/           # Logique métier
│   │   ├── entities/
│   │   ├── usecases/
│   │   └── repositories/
│   ├── data/             # Couche de données
│   │   ├── database/     # WatermelonDB
│   │   ├── api/          # Supabase
│   │   └── cache/
│   ├── presentation/     # UI & UX
│   │   ├── screens/
│   │   ├── components/
│   │   ├── navigation/
│   │   └── hooks/
│   ├── core/             # Types & utils
│   ├── services/         # Services externes
│   └── styles/           # Thème & design
├── assets/
├── app.json
└── package.json
```

### Navigation
```typescript
RootStack
├── MainTabs
│   ├── ExploreTab (MapScreen)
│   ├── DiscoverTab (DiscoverScreen)
│   ├── DirectionsTab (DirectionsScreen)
│   ├── AssistantTab (AssistantScreen)
│   └── ProfileTab (ProfileScreen)
├── PlaceDetailModal
├── PaywallModal
└── OnboardingFlow
```

---

## 📱 Écrans Principaux

### 1. MapScreen (Explore)
- **Carte Mapbox** avec style Tokyo personnalisé
- **POI clustérisés** pour performance
- **Filtres**: quartiers, catégories, prix
- **Bottom sheet** animé pour détails
- **Mode offline** avec tuiles téléchargées

### 2. AssistantScreen (Chat IA)
- **Interface conversationnelle** fluide
- **Questions suggérées** par contexte
- **Quota management** (3 gratuit/jour)
- **POI suggestions** intégrées
- **Mode dégradé** offline

### 3. DiscoverScreen
- **Collections thématiques** curées
- **Tendances** et nouveautés
- **Filtres avancés** multi-critères
- **Favoris** et listes personnalisées

### 4. DirectionsScreen
- **Itinéraires optimisés** Tokyo
- **Multi-modal**: train, métro, marche
- **Temps réel** avec API transport
- **Mode offline** basique

### 5. ProfileScreen
- **Badge Pro** animé
- **Statistiques** d'utilisation
- **Paramètres** et préférences
- **Support** et feedback

---

## 🔧 Services & Intégrations

### 1. WatermelonDB (Offline-First)
```typescript
// Modèles principaux
- POI: lieux avec coordonnées, tags, descriptions
- User: préférences et quota
- MapTile: cache des tuiles carte
- SyncQueue: opérations en attente
```

### 2. Synchronisation Supabase
- **Sync bidirectionnelle** avec résolution de conflits
- **Queue offline** avec retry exponentiel
- **Delta sync** pour optimisation
- **Compression** des payloads

### 3. Service IA (RAG Agent)
```typescript
// Edge Function Supabase
- Contexte Tokyo enrichi
- Réponses personnalisées
- Suggestions de POI
- Support multilingue
```

### 4. Paiement RevenueCat
- **Achat unique** Pro
- **Restauration** cross-platform
- **Analytics** de conversion
- **Webhooks** pour backend

### 5. Animations Reanimated
- **Bottom sheets** gestuels
- **Transitions** entre écrans
- **Feedback** utilisateur
- **60 FPS** constant

---

## 🚀 Guide de Démarrage

### 1. Installation
```bash
# Cloner le projet
git clone https://github.com/votre-repo/yorimichi-app
cd yorimichi-app

# Installer les dépendances
npm install

# iOS uniquement
cd ios && pod install
```

### 2. Configuration
```bash
# Créer .env avec vos clés
cp .env.example .env

# Variables requises:
EXPO_PUBLIC_SUPABASE_URL=
EXPO_PUBLIC_SUPABASE_ANON_KEY=
EXPO_PUBLIC_MAPBOX_ACCESS_TOKEN=
EXPO_PUBLIC_REVENUECAT_IOS_KEY=
EXPO_PUBLIC_REVENUECAT_ANDROID_KEY=
```

### 3. Développement
```bash
# Démarrer le serveur
npm start

# iOS
npm run ios

# Android
npm run android

# Tests
npm test
```

### 4. Build Production
```bash
# EAS Build
eas build --platform all --profile production

# Submit aux stores
eas submit
```

---

## 📊 Métriques de Succès

### Performance
- **Temps de démarrage**: < 2s
- **FPS**: 60 constant
- **Taille bundle**: < 50MB
- **Cache offline**: 500MB max

### Business
- **Conversion gratuit→Pro**: 5% cible
- **Rétention J7**: 40%
- **Questions IA/jour**: 10 moyenne Pro
- **Note App Store**: 4.5+ étoiles

### Qualité
- **Crash-free rate**: > 99.5%
- **Test coverage**: > 80%
- **Accessibility**: WCAG AA
- **Localization**: EN/FR/JP

---

## 🔐 Sécurité & Conformité

### Données Utilisateur
- **Chiffrement** at rest et in transit
- **Anonymisation** des analytics
- **RGPD** compliant
- **Pas de tracking** invasif

### API & Backend
- **Row Level Security** Supabase
- **Rate limiting** sur Edge Functions
- **Validation** côté serveur
- **Monitoring** des anomalies

---

## 📈 Roadmap Post-MVP

### V1.1 (1 mois)
- Widget iOS accueil
- Apple Watch companion
- Partage social basique
- Mode sombre

### V1.2 (2 mois)  
- Autres villes (Kyoto, Osaka)
- Réservations restaurants
- Photos communautaires
- Traduction temps réel

### V2.0 (6 mois)
- Réalité augmentée
- Guides audio
- Marketplace créateurs
- API partenaires

---

## 🤝 Équipe & Ressources

### Contacts Clés
- **Product Owner**: [Email]
- **Tech Lead**: [Email]
- **Design Lead**: [Email]
- **Support**: support@yorimichi.app

### Documentation
- [Architecture détaillée](./docs/ARCHITECTURE.md)
- [Guide de contribution](./docs/CONTRIBUTING.md)
- [API Reference](./docs/API.md)
- [Design System](./docs/DESIGN_SYSTEM.md)

### Outils
- **Projet**: Linear/Jira
- **Design**: Figma
- **CI/CD**: GitHub Actions + EAS
- **Monitoring**: Sentry + LogRocket

---

## ✅ Checklist Lancement

### Développement
- [x] Structure projet Expo
- [x] Navigation complète
- [x] Design System Tokyo Metro
- [x] MapScreen avec Mapbox
- [x] AssistantScreen chat IA
- [x] WatermelonDB offline
- [x] Sync Supabase
- [x] Animations Reanimated
- [x] Paiement RevenueCat
- [ ] Tests E2E complets

### Design
- [ ] Icônes app finales
- [ ] Screenshots stores
- [ ] Vidéo promo
- [ ] Site web landing

### Backend
- [ ] Edge Functions déployées
- [ ] Base de données seedée
- [ ] Monitoring configuré
- [ ] Backups automatiques

### Business
- [ ] Compte développeur Apple
- [ ] Compte Google Play
- [ ] RevenueCat configuré
- [ ] Analytics tracking plan

### Marketing
- [ ] Description stores optimisée
- [ ] Keywords ASO
- [ ] Press kit
- [ ] Social media

---

## 🎉 Conclusion

Yorimichi est maintenant prêt pour le développement ! Cette documentation complète vous guidera à travers toutes les étapes de création de l'application.

**Points forts du projet**:
- ✨ Architecture solide et scalable
- 🎨 Design unique inspiré du métro de Tokyo
- ⚡ Performance optimale avec offline-first
- 🤖 IA intelligente et contextuelle
- 💰 Monétisation simple et efficace

**Prochaines étapes**:
1. Configurer l'environnement de développement
2. Implémenter les fonctionnalités manquantes
3. Tester intensivement
4. Préparer le lancement

Bonne chance pour faire de Yorimichi le guide de référence pour Tokyo ! 🗾🎌

---

*"Yorimichi - Transformez vos détours en découvertes"*