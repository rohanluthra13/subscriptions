# HTML-Over-Wire Refactor Plan

## Overview
This document outlines the systematic refactor from the current hybrid JavaScript approach to pure HTML-over-wire architecture for the subscription manager.

## Changes Required

### 1. Remove Client-Side Data Caching
- **Complexity**: Low - simple deletion of JavaScript objects
- **Files**: `templates/views/manage.html` lines 754-777
- **Why**: Eliminates sync issues, single source of truth
- **Change**: Delete `subscriptionsData` and `categoriesData` JavaScript objects

### 2. Convert Modals to Server-Rendered Pages/Fragments
- **Complexity**: High - new endpoints, form handling, navigation flow
- **Files**: `main.py` (+5 new endpoints), `templates/views/manage.html` (major rewrite)
- **Why**: Moves form population logic server-side
- **Change**: Replace JavaScript modal population with server-rendered forms

### 3. Replace JavaScript Form Handlers with Server Submissions
- **Complexity**: Medium - convert AJAX to standard form posts
- **Files**: `templates/views/manage.html` (form elements), `main.py` (endpoint changes)
- **Why**: Business logic belongs server-side only
- **Change**: Convert AJAX form submissions to standard HTTP form posts

### 4. Move Dropdown Rendering to Server
- **Complexity**: Medium - server-side HTML generation, styling preservation
- **Files**: `main.py` (dropdown rendering), `templates/views/manage.html` (markup changes)
- **Why**: Server controls all content generation
- **Change**: Render dropdown options server-side instead of JavaScript building

### 5. Convert Inline Editing to Page Navigation
- **Complexity**: Low - remove toggle handlers, add edit links
- **Files**: `templates/views/manage.html` (remove toggles), `main.py` (+2 edit pages)
- **Why**: Eliminates client-side state management
- **Change**: Replace toggle switches and inline fields with edit page navigation

### 6. Replace Fragment Updates with Full Page Loads
- **Complexity**: Low - remove AJAX refresh functions
- **Files**: `templates/views/manage.html` (remove `refreshSubscriptionCards`)
- **Why**: Eliminates event reattachment complexity
- **Change**: Remove `refreshSubscriptionCards()` and similar fragment update functions

### 7. Server-Side Review Filtering
- **Complexity**: Medium - URL parameter handling, server-side filtering logic
- **Files**: `main.py` (filter logic), `templates/views/review.html` (remove JS filtering)
- **Why**: Stateless, bookmarkable filtering
- **Change**: Move todo/done filtering from JavaScript to URL parameters

### 8. Remove Dynamic DOM Generation
- **Complexity**: Low - replace with server-rendered forms
- **Files**: `templates/views/notepad.html` (remove `addNote()`), `main.py` (note endpoints)
- **Why**: Security and simplicity
- **Change**: Replace JavaScript HTML creation with server-rendered content

### 9. Simplify Navigation JavaScript
- **Complexity**: Low - keep only view loading, remove initialization complexity
- **Files**: `templates/base.html` (streamline navigation JS)
- **Why**: Reduce to core navigation only
- **Change**: Remove complex view initialization, keep only basic view loading

## Implementation Order

### Phase 1: Foundation (Low Risk)
1. **Remove Dynamic DOM Generation** - Simple deletion, isolated impact
2. **Simplify Navigation JavaScript** - Clean up base template first
3. **Remove Client-Side Data Caching** - Eliminates sync issues early

### Phase 2: Server-Side Logic (Medium Risk)
4. **Server-Side Review Filtering** - Self-contained feature, good practice
5. **Move Dropdown Rendering to Server** - Affects forms but contained scope

### Phase 3: Form Handling (Medium Risk)
6. **Replace JavaScript Form Handlers** - Convert AJAX to standard posts
7. **Convert Inline Editing to Page Navigation** - Simple edit flows

### Phase 4: Major Restructure (High Risk)
8. **Convert Modals to Server-Rendered Pages** - Biggest change, do last
9. **Replace Fragment Updates with Full Page Loads** - Final cleanup

## Implementation Strategy

**Why This Order:**
- **Early wins**: Remove complexity first (phases 1-2)
- **Build momentum**: Each phase makes the next easier
- **Reduce interdependencies**: Forms work before tackling modals
- **Test incrementally**: App stays functional throughout
- **Save hardest for last**: Modal conversion when everything else is simplified

**Key Principle**: Start by **removing** complexity before **adding** new patterns. This approach maintains working software while systematically moving toward HTML-over-wire architecture.