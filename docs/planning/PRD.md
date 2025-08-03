# Automated Subscription Manager PRD

### TL;DR

Automated Subscription Manager is a consumer-focused tool that connects to a user's Gmail account, uses large language models (LLMs) to identify and classify subscription-related emails, and extracts key subscription data into a local database. Users can view, search, and manage their subscriptions through a simple web dashboard, helping them save money and avoid unwanted renewals.

---

## Goals

### Business Goals

* Build a foundation for future integrations (e.g., other email providers, direct subscription cancellation).

### User Goals

* Effortlessly discover all active subscriptions from their Gmail inbox.

* Receive clear, actionable insights about upcoming renewals and costs.

* Easily track, search, and manage subscriptions in one place.

* Maintain privacy and control over their data.

### Non-Goals

* Directly cancel or modify subscriptions on behalf of the user (initial release).

* Support for non-Gmail email providers (e.g., Outlook, Yahoo) at launch.

* Mobile app or native desktop application (web dashboard only for MVP).

---

## User Stories

**Persona 1: Budget-Conscious Consumer (Alex)**

* As a consumer, I want to see all my active subscriptions in one place, so that I can avoid paying for services I no longer use.

* As a consumer, I want to be notified of upcoming renewals, so that I can cancel unwanted subscriptions before being charged.

* As a consumer, I want to search and filter my subscriptions by cost or category, so that I can better understand my spending.

**Persona 2: Privacy-Focused User (Jordan)**

* As a privacy-focused user, I want to know exactly what data is being accessed and stored, so that I feel secure using the product.

* As a privacy-focused user, I want to be able to delete my data at any time, so that I retain control over my information.

**Persona 3: Occasional User (Taylor)**

* As an occasional user, I want a simple onboarding process, so that I can get started quickly without technical knowledge.

* As an occasional user, I want to export my subscription data, so that I can use it elsewhere if needed.

---

## Functional Requirements

* **Email Integration (Priority: High)**

  * Gmail OAuth authentication: Securely connect and authorize access to user’s Gmail inbox.

  * Email ingestion: Fetch relevant emails (e.g., receipts, confirmations, renewal notices).

  * Incremental sync: Periodically check for new subscription emails.

* **Subscription Detection & Extraction (Priority: High)**

  * LLM-based classification: Identify subscription-related emails using LLMs.

  * Data extraction: Parse and extract key fields (service name, cost, renewal date, frequency, cancellation info).

  * Deduplication: Merge duplicate subscriptions from multiple emails.

* **Local Database & Data Management (Priority: High)**

  * Store extracted subscription data locally (on user’s device or secure cloud instance).

  * CRUD operations: Allow users to edit, delete, or annotate subscriptions.

* **Web Dashboard (Priority: High)**

  * Subscription list: Display all detected subscriptions with key details.

  * Search & filter: Enable users to search, sort, and filter subscriptions.

  * Renewal calendar: Visualize upcoming renewals and payment dates.

  * Export: Allow users to export their subscription data (CSV/JSON).

* **Notifications & Insights (Priority: Medium)**

  * Renewal reminders: Notify users of upcoming charges.

  * Spending summary: Aggregate and visualize monthly/annual subscription costs.

* **Privacy & Security (Priority: High)**

  * Data deletion: Allow users to delete all stored data.

  * Transparent privacy policy: Clearly communicate data usage and storage.

* **Settings & Account Management (Priority: Medium)**

  * Manage connected Gmail accounts.

  * User profile and preferences.

---

## User Experience

**Entry Point & First-Time User Experience**

* Users discover the product via website, referral, or app store listing.

* Landing page explains value proposition and privacy assurances.

* Onboarding flow prompts user to sign in with Google (OAuth).

* Consent screen details data access and privacy policy.

* Optional quick tutorial highlights dashboard features.

**Core Experience**

* **Step 1:** User connects Gmail account.

  * Minimal friction: Single-click Google sign-in.

  * Error handling for failed authentication or denied permissions.

  * Success confirmation and progress indicator for email ingestion.

* **Step 2:** System ingests and processes emails.

  * Progress bar or spinner shows status.

  * User is informed of estimated time for initial scan.

* **Step 3:** Dashboard displays detected subscriptions.

  * Clear, sortable list with service name, cost, renewal date, and status.

  * Visual indicators for upcoming renewals or missing data.

* **Step 4:** User interacts with subscriptions.

  * Edit, annotate, or delete entries.

  * Search and filter by service, cost, or renewal date.

  * Export data via download button.

* **Step 5:** User receives notifications (if enabled).

  * Email or in-app reminders for upcoming renewals.

  * Monthly summary of subscription spending.

* **Step 6:** User manages account and privacy.

  * Access settings to disconnect Gmail, delete data, or adjust preferences.

**Advanced Features & Edge Cases**

* Power users can manually add or correct subscription entries.

* Error states for failed email sync, LLM misclassification, or data extraction issues.

* Graceful handling of Gmail API rate limits or outages.

* Support for users with large inboxes (progressive loading, batching).

**UI/UX Highlights**

* Clean, uncluttered dashboard with high contrast and accessible fonts.

* Responsive design for desktop and tablet.

* Clear call-to-action buttons and feedback for all user actions.

* Tooltips and contextual help for new users.

* Privacy and data usage reminders in settings.

---

## Narrative

Alex, a busy professional, subscribes to multiple streaming services, productivity tools, and newsletters. Over time, Alex loses track of which subscriptions are active, how much is being spent, and when renewals are due. This leads to surprise charges and wasted money on unused services.

After discovering the Automated Subscription Manager, Alex quickly connects their Gmail account through a secure, privacy-focused onboarding process. Within minutes, the dashboard displays a comprehensive list of all active subscriptions, complete with costs, renewal dates, and helpful insights. Alex can easily filter subscriptions, set up renewal reminders, and export the data for budgeting.

With newfound clarity, Alex cancels unnecessary subscriptions before renewal, saves money, and feels more in control of personal finances. The business benefits from high user engagement, positive word-of-mouth, and a growing user base eager for future features like direct cancellation and multi-email support.

---

## Success Metrics

### User-Centric Metrics

* Number of active users (measured weekly/monthly)

* User retention rate after 30 and 90 days

* Net Promoter Score (NPS) or user satisfaction survey results

* Percentage of users who set up renewal reminders

### Business Metrics

* Conversion rate from free to paid tier

* Churn rate (users disconnecting Gmail or deleting data)

* Cost per acquisition (CPA) and customer lifetime value (CLV)

### Technical Metrics

* Email ingestion and processing success rate (>98%)

* Average time to complete initial email scan (<5 minutes for 95% of users)

* System uptime (>99.5%)

* Data extraction accuracy (measured by manual QA sampling)

### Tracking Plan

* User sign-ups and Gmail connections

* Email ingestion start/completion events

* Subscription detection and extraction events

* Dashboard interactions (search, filter, export)

* Notification opt-ins and sends

* Data deletion/account disconnect events

---

## Technical Considerations

### Technical Needs

* Gmail API integration for secure email access

* LLM-based email classification and data extraction pipeline

* Local or secure cloud database for storing subscription data

* Web dashboard (front-end) for user interaction

* Notification system (email or in-app)

### Integration Points

* Google OAuth for authentication and Gmail API access

* Optional analytics and error tracking tools (e.g., Sentry, Mixpanel)

### Data Storage & Privacy

* Store only essential subscription data, not full email content

* Encrypt all stored data at rest and in transit

* Comply with GDPR and CCPA for data privacy and user rights

* Provide clear data deletion and export options

### Scalability & Performance

* Support for thousands of users with varying inbox sizes

* Efficient, incremental email sync to minimize API usage and latency

* Scalable LLM inference (batch processing, caching)

### Potential Challenges

* Handling Gmail API rate limits and quota restrictions

* Ensuring high accuracy in LLM-based extraction across diverse email formats

* Maintaining user trust through robust privacy and security practices

* Managing edge cases (e.g., shared inboxes, non-English emails)

---

## Milestones & Sequencing

### Project Estimate

* Medium: 3–5 weeks for MVP

### Team Size & Composition

* Small Team: 2 people

  * 1 Full-stack Engineer (handles back-end, front-end, and integrations)

  * 1 Product/Design Lead (handles UX, UI, and product management)

### Suggested Phases

**Phase 1: Core MVP Build (2 weeks)**

* Key Deliverables: Gmail integration, LLM-based extraction, local database, basic dashboard (Engineer)

* Dependencies: Google API access, LLM model selection

**Phase 2: UX Polish & Notifications (1 week)**

* Key Deliverables: Dashboard enhancements, search/filter, renewal reminders, onboarding flow (Product/Design Lead, Engineer)

* Dependencies: Core MVP completion

**Phase 3: Privacy, Export, and QA (1–2 weeks)**

* Key Deliverables: Data deletion/export, privacy policy, manual QA, bug fixes (Engineer, Product/Design Lead)

* Dependencies: Phase 2 completion

**Phase 4: Launch & Feedback (ongoing)**

* Key Deliverables: Public launch, user support, analytics tracking, rapid iteration (Both)

* Dependencies: MVP readiness

---