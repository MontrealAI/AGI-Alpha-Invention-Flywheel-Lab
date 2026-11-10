# Your data / Vos données

## English

**Core browser mode.** The application works with data in the current browser and the project files you choose to open or download. Browser storage is a convenience, not encrypted backup. It may be unavailable in a private session or when opening local files, and can change when a folder moves. Export a project file before closing important work. A downloaded project can contain your mission, pasted model outputs, sources, assumptions and results; review it before sharing.

**Manual model use.** Copying a prompt into an external chat service sends that text to the service you select. Importing the response back does not undo that disclosure. Remove confidential information unless you have authority and an appropriate provider arrangement.

**Optional bridge.** The bridge runs locally. Configured model requests leave the device for the selected endpoint; a local inference endpoint may still have its own network behavior. Public-source retrieval sends requests to the source hosts. Provider/source privacy policies apply. Credentials belong in environment variables and private configuration outside the distribution, never in project exports.

**Deletion and recovery.** Delete exported files through your operating system. Clear the relevant browser storage through your browser when you want to remove local saved state. This does not remove data already sent to a provider, copied elsewhere or backed up by your own software. No account-wide or provider deletion is performed by the HARNESS.

No hosted project-sync service, telemetry service or encrypted vault is included in this candidate. Independently inspect the included source and the release evidence when assessing suitability for sensitive work.

## Français

Le mode principal traite vos données dans le navigateur et dans les fichiers de projet que vous ouvrez ou téléchargez. Le stockage du navigateur n'est ni chiffré ni une sauvegarde garantie. Exportez les travaux importants et examinez les fichiers avant de les partager.

Copier une demande dans un service d'IA externe communique ce texte au service choisi. Utilisez seulement des renseignements que vous êtes autorisé à transmettre. Le connecteur local facultatif envoie les demandes au fournisseur configuré; ses règles de confidentialité s'appliquent. Les clés restent dans l'environnement local et hors des projets.

Pour supprimer vos copies locales, effacez les fichiers et les données correspondantes du navigateur. Cela ne supprime pas les informations déjà transmises à un fournisseur ou sauvegardées ailleurs. Cette version candidate n'inclut ni synchronisation hébergée des projets, ni service de télémétrie, ni coffre chiffré.

## Persistent workflows and official account authorization

The local connector's workspace contains goals, model responses, constructed files, tests and checkpoints. Keep it private and back it up separately; it is not automatically encrypted. Exports can include sensitive mission content even when credentials are excluded.

Official OAuth credentials remain outside project and release archives. Use the connection's disconnect control and the provider's account controls for revocation; disconnecting locally and revoking provider-side access are different operations. Refresh tokens and account identity must never appear in prompt context, screenshots, reports or exported evidence.

Plan usage, API billing and Codex operation retain their separate provider terms. Nothing in this package grants the publisher access to a customer's account. No hosted project synchronization or telemetry is introduced.

### Français

L’espace de travail contient objectifs, réponses, fichiers construits, tests et points de reprise. Il est privé, mais pas automatiquement chiffré. Sauvegardez-le séparément et inspectez les exports avant partage. Les identifiants OAuth restent hors des projets et archives. Déconnecter localement et révoquer l’accès chez le fournisseur sont deux opérations distinctes. Aucun jeton ne doit apparaître dans une demande, capture ou preuve exportée.
