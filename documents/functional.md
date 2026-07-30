# Exigences fonctionnelles — Système de Gestion de Boutique

**Stack technique :** Python, Django, Tailwind CSS (build Node), Chart.js
**Périmètre :** Gestion de boutique multi-agences avec prix/stock par agence, transferts de stock, reçus, clients et accès basé sur les rôles.

Chaque exigence est numérotée (EF-x) et regroupée par module, dans l'ordre de construction du système.

---

## 1. Gestion des agences

- **EF-1.1** Le système doit permettre à un Admin de créer, modifier et désactiver des agences (nom, adresse, téléphone, statut actif).
- **EF-1.2** Chaque fiche produit, niveau de stock, utilisateur, commande et transfert de stock doit être rattaché à une ou plusieurs agences — aucune donnée n'existe hors du contexte d'une agence, à l'exception du catalogue produit global et des paramètres de l'entreprise.
- **EF-1.3** Une agence désactivée doit être exclue des écrans de vente/POS mais rester visible dans l'historique et les rapports.

## 2. Gestion des catégories

- **EF-2.1** Le système doit permettre aux Admins de créer, modifier et désactiver des catégories (nom, slug, image, statut actif).
- **EF-2.2** Les catégories doivent supporter un parent optionnel, permettant des sous-catégories imbriquées.
- **EF-2.3** Le système doit supporter l'import en masse de catégories via CSV/Excel, avec une colonne de nom du parent pour établir l'imbrication, et un rapport de validation indiquant les lignes réussies ou échouées.

## 3. Gestion des produits (catalogue global)

- **EF-3.1** Le système doit permettre aux Admins de créer, modifier et désactiver des produits dans un catalogue global unique (nom, SKU/code-barres, catégorie, unité, image, description, statut actif).
- **EF-3.2** Le prix et le stock d'un produit ne doivent **pas** être stockés sur le produit lui-même — ils sont spécifiques à chaque agence (voir Section 4).
- **EF-3.3** Le système doit supporter l'import en masse de produits via CSV/Excel pour le catalogue de base, avec validation ligne par ligne et rapport d'erreurs.

## 4. Prix & stock par agence (BranchProduct)

- **EF-4.1** Le système doit maintenir une fiche par agence pour chaque produit (`BranchProduct`) contenant : prix de vente, prix de revient, quantité en stock, seuil d'alerte de stock bas et statut actif, unique par couple `(produit, agence)`.
- **EF-4.2** Une agence doit pouvoir fixer un prix différent des autres agences pour le même produit, et peut choisir de ne pas proposer un produit donné (fiche inactive).
- **EF-4.3** Le système doit supporter l'import en masse des prix/stocks par agence (séparé de l'import du catalogue de base), avec validation et rapport d'erreurs.
- **EF-4.4** Le système doit détecter quand le stock d'une agence pour un produit passe sous son seuil d'alerte configuré, et le signaler sur le tableau de bord/les alertes.
- **EF-4.5** Le système doit supporter l'export des niveaux de stock actuels (filtrable par agence et/ou catégorie) en CSV/Excel.

## 5. Transfert de stock

- **EF-5.1** Le système doit permettre à un Responsable d'agence ou à un Admin de demander un transfert de stock d'un produit d'une agence source vers une agence destination, en précisant la quantité.
- **EF-5.2** Un transfert de stock doit enregistrer qui l'a demandé et, optionnellement, qui l'a approuvé, ainsi que son statut (ex. en attente, approuvé, terminé, annulé) et la date du transfert.
- **EF-5.3** À la finalisation, un transfert doit déduire la quantité transférée du stock `BranchProduct` de l'agence source et l'ajouter au stock `BranchProduct` de l'agence destination (en créant la fiche de destination si elle n'existe pas encore).
- **EF-5.4** Un transfert ne doit pas pouvoir être finalisé si l'agence source ne dispose pas d'un stock suffisant au moment de l'exécution.

## 6. Gestion des clients

- **EF-6.1** Une vente doit supporter un client optionnel — une vente sans aucune information client (« client de passage ») doit être totalement valide.
- **EF-6.2** Au point de vente, le caissier doit pouvoir soit sélectionner un client existant (recherche par nom ou téléphone), soit saisir directement le nom et le téléphone d'un nouveau client dans le formulaire de vente.
- **EF-6.3** Si le numéro de téléphone saisi ne correspond à aucun client existant, le système doit créer automatiquement une nouvelle fiche `Client` au moment où la vente est confirmée.
- **EF-6.4** Le numéro de téléphone doit servir de clé naturelle pour éviter les doublons de fiches client lorsque le même client est servi à nouveau sous une orthographe de nom légèrement différente.

## 7. Commandes / Ventes (POS)

- **EF-7.1** Un caissier doit pouvoir rechercher des produits et les ajouter au panier, le prix et le stock disponible reflétant toujours l'agence propre au caissier.
- **EF-7.2** Le système doit supporter l'application d'une remise et d'une taxe sur une commande, ainsi que la sélection d'un mode de paiement (espèces, carte, mobile money, etc.).
- **EF-7.3** À la confirmation de la commande, le système doit : déduire le stock des fiches `BranchProduct` concernées, créer la `Commande` et ses lignes `LigneCommande`, et déclencher la génération du reçu — le tout dans une seule opération atomique.
- **EF-7.4** Chaque `LigneCommande` doit enregistrer le prix unitaire au moment de la vente (figé à partir de `BranchProduct`), afin que les changements de prix ultérieurs ne modifient pas les données historiques des commandes/reçus.
- **EF-7.5** Les commandes doivent avoir un cycle de vie de statut : en attente, terminée, remboursée, annulée.
- **EF-7.6** Les caissiers ne doivent voir que leur propre historique de ventes ; les Responsables d'agence et les Admins doivent voir les ventes limitées à leur(s) agence(s) ou globalement, respectivement.

## 8. Génération des reçus

- **EF-8.1** Un reçu doit être généré automatiquement et exclusivement à partir d'une commande terminée (relation un-à-un), avec un numéro de reçu unique.
- **EF-8.2** Le reçu doit être disponible en PDF téléchargeable et en vue HTML imprimable, tous deux utilisant l'en-tête de l'entreprise (logo, nom, adresse, numéro fiscal).
- **EF-8.3** Les reçus doivent pouvoir être retrouvés ultérieurement par numéro de reçu ou par ID de commande.

## 9. Utilisateurs & rôles

- **EF-9.1** Le système doit supporter trois rôles d'utilisateur héritant d'un profil commun `Utilisateur` : Admin, Responsable d'agence (`ResponsableAgence`) et Caissier.
- **EF-9.2** Les Admins doivent avoir un accès sans restriction à toutes les agences, catégories, produits, utilisateurs et rapports.
- **EF-9.3** Les Responsables d'agence doivent être limités à leur agence assignée pour la gestion des prix/stocks, la gestion des caissiers et les rapports au niveau de l'agence.
- **EF-9.4** Les Caissiers doivent être limités à la création de ventes/reçus et à la consultation de leur propre historique de ventes au sein de leur agence assignée.
- **EF-9.5** Tout accès aux données doit être appliqué à la fois au niveau des vues/permissions et au niveau des querysets (ne pas se reposer uniquement sur le masquage dans l'interface).

## 10. Paramètres de l'entreprise

- **EF-10.1** Le système doit maintenir un enregistrement unique et global des paramètres de l'entreprise (nom, logo, slogan, adresse, téléphone, email, site web, numéro fiscal, symbole monétaire, note de bas de reçu), appliqué comme singleton.
- **EF-10.2** Les paramètres de l'entreprise doivent être disponibles automatiquement dans chaque template via un context processor, sans que chaque vue n'ait besoin de les transmettre explicitement.
- **EF-10.3** Toute mise à jour des paramètres de l'entreprise doit invalider immédiatement toute copie mise en cache, afin que les changements (ex. un nouveau logo) apparaissent sans délai.

## 11. Interface d'administration Django

- **EF-11.1** Tous les modèles principaux (Agence, Catégorie, Produit, BranchProduct, TransfertStock, Client, Commande, LigneCommande, Reçu, ParametresEntreprise, profils utilisateur) doivent être enregistrés dans l'admin Django avec des filtres de liste et champs de recherche appropriés.
- **EF-11.2** Les lignes de commande doivent être modifiables en ligne sur la page admin de la Commande ; les prix/stocks par agence doivent être modifiables en ligne sur la page admin du Produit.
- **EF-11.3** Les paramètres de l'entreprise doivent être restreints dans l'admin à une seule instance (pas d'option « ajouter » une fois qu'une instance existe).

## 12. Tableau de bord & rapports

- **EF-12.1** Le système doit afficher les ventes dans le temps (journalier/hebdomadaire/mensuel), filtrable par agence et plage de dates, avec Chart.js.
- **EF-12.2** Le tableau de bord doit afficher le chiffre d'affaires par rapport au coût/à la marge, les produits les plus vendus, les catégories les plus vendues, et une répartition des ventes par mode de paiement.
- **EF-12.3** Le tableau de bord doit afficher des indicateurs de santé du stock (nombre de produits en stock bas et en rupture).
- **EF-12.4** Les Admins doivent avoir accès à une vue de comparaison des agences montrant les ventes côte à côte entre agences.

## 13. Exigences non fonctionnelles

- **EF-13.1 (Performance)** Les requêtes impliquant des objets liés doivent utiliser `select_related` ou `prefetch_related` selon le cas pour éviter les problèmes N+1 (ex. Commande→Caissier/Agence, Commande→LigneCommandes, Produit→BranchProduct).
- **EF-13.2 (Cache)** Les agrégats du tableau de bord, les listes de produits/catégories et les paramètres de l'entreprise doivent être mis en cache, avec une invalidation du cache liée aux signals des modèles concernés.
- **EF-13.3 (Pagination)** Les listes de produits, l'historique des commandes et les résultats d'import en masse doivent être paginés.
- **EF-13.4 (Signals)** La déduction de stock, le recalcul des totaux de commande, la génération de reçus, la détection de stock bas et l'invalidation du cache doivent être implémentés via des signals Django (`post_save`/`post_delete`) plutôt que par une logique dupliquée dans les vues.
- **EF-13.5 (Architecture)** La logique métier (déduction de stock, règles de tarification, calcul des totaux) doit vivre dans une couche de service séparée des vues, pour rester testable et réutilisable.
- **EF-13.6 (Classe de base)** Tous les modèles du domaine doivent hériter d'une classe abstraite commune `BaseModel` fournissant `id`, `created_at` et `updated_at`.
- **EF-13.7 (Responsive)** L'interface doit être responsive, avec une vue POS adaptée au mobile pour les caissiers et un tableau de bord orienté desktop pour les admins/responsables.