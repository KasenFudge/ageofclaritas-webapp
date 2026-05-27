graph TD
    %% Define Styles
    classDef rulebook fill:#E6D537,stroke:#333,stroke-width:2px,color:#000;
    classDef accounts fill:#1d3557,stroke:#333,stroke-width:2px,color:#fff;
    classDef events fill:#457b9d,stroke:#333,stroke-width:2px,color:#fff;
    classDef payments fill:#004b23,stroke:#333,stroke-width:2px,color:#fff;
    classDef surveys fill:#6a0dad,stroke:#333,stroke-width:2px,color:#fff;

    RB[Rulebook App<br><i>Rulebook Reference</i>]:::rulebook
    
    
    RB ~~~ Accounts
    RB ~~~ Events

    subgraph Accounts [Account Pages]
        ACC[User Account / Profile]:::accounts
        EDASH[User Dashboard<br><i>Upcoming Events</i>]:::accounts
    end

    subgraph Events [Event Management]
        UEV[Upcoming Events]:::events
        EREG[Event Registration]:::events
    end

    subgraph Payments [Payment Gateway]
        PAY[Payments App<br><i>Stripe Session</i>]:::payments
        TICK[Ticket System]:::payments
    end

    subgraph Surveys [Post-Event Surveys]
        SRV[Surveys App]:::surveys
    end
    
    EREG -->|Reflects On| EDASH
    ACC -->|Views Registrations| EDASH
    
    UEV -->|Dictates Active Events| EREG
    PAY -->|Updates Status| TICK
    ACC -->|Registers for Event| EREG
    EREG -->|Optional: Auto-Redirects| PAY
    EDASH -->|Pay Unpaid Tickets| PAY
    
    TICK -->|Reflects On| EDASH
    UEV -->|Creates Post-Event Survey| SRV
    EDASH -->|Link to Active Surveys| SRV
