graph TB
    %% Core Django App Clusters
    
    subgraph CoreApp [Core & Auth]
        Accounts[Accounts App<br>Custom User & Profiles]
    end

    subgraph Gameplay [Game Rules engine]
        Rulebook[Rulebook App<br>Kin, Talents, Classes]
        Events[Events App<br>Campaigns & Sessions]
    end

    subgraph Commerce [Billing Stack]
        Payments[Payments App<br>Stripe & Checkout]
    end

    %% High-Level Cross-App Dependencies
    Payments -->|Unlocks Access| Accounts
    Events -->|Requires Active Profile for Registration| Accounts

    %% Styling for visual clarity
    style CoreApp fill:#2d3748,stroke:#4a5568,stroke-width:2px
    style Gameplay fill:#1a202c,stroke:#ffd700,stroke-width:2px
    style Commerce fill:#2c3e50,stroke:#27ae60,stroke-width:2px