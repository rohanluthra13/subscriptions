"""
HTML Templates for Subscription Manager Web Interface

All HTML/CSS templates extracted from main.py for better readability.
Templates use Windows 98 theme styling.
"""

def get_dashboard_template(connections_html, subscriptions):
    """Main dashboard HTML template with Windows 98 styling"""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Subscription Manager</title>
    <style>
        /* Windows 98 Theme - Adapted from 98.css */
        
        /* Font Faces */
        @font-face {{
            font-family: "Pixelated MS Sans Serif";
            src: url(/fonts/ms_sans_serif.woff) format("woff");
            src: url(/fonts/ms_sans_serif.woff2) format("woff2");
            font-weight: 400;
        }}
        @font-face {{
            font-family: "Pixelated MS Sans Serif";
            src: url(/fonts/ms_sans_serif_bold.woff) format("woff");
            src: url(/fonts/ms_sans_serif_bold.woff2) format("woff2");
            font-weight: 700;
        }}
        
        /* Base Styles */
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            background: #008080;  /* Classic teal desktop */
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            color: #000;
            margin: 0;
            padding: 20px;
            -webkit-font-smoothing: none;
        }}
        
        /* Window Component */
        .window {{
            background: #c0c0c0;
            border: 2px solid;
            border-color: #ffffff #0a0a0a #0a0a0a #ffffff;
            box-shadow: inset -1px -1px #0a0a0a, inset 1px 1px #dfdfdf, inset -2px -2px grey, inset 2px 2px #fff;
            margin-bottom: 20px;
            position: relative;
            min-width: 200px;
            min-height: 150px;
        }}
        
        /* Title Bar */
        .title-bar {{
            background: linear-gradient(90deg, #000080, #1084d0);
            padding: 3px 2px 3px 3px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: bold;
            color: white;
        }}
        
        .title-bar-text {{
            padding: 0 0 0 3px;
            font-weight: bold;
            color: white;
            letter-spacing: 0;
        }}
        
        .title-bar-controls {{
            display: flex;
        }}
        
        .title-bar-controls button {{
            padding: 0;
            display: block;
            min-width: 16px;
            min-height: 14px;
            margin-left: 2px;
            font-size: 12px;
            line-height: 1;
            background: #c0c0c0;
            color: #000;
            cursor: pointer;
        }}
        
        .title-bar-controls button:hover {{
            background: #dfdfdf;
        }}
        
        .title-bar-controls button:active {{
            background: #a0a0a0;
            box-shadow: inset 1px 1px #808080, inset -1px -1px #fff;
        }}
        
        /* Window Body */
        .window-body {{
            margin: 8px;
        }}
        
        /* Buttons */
        button {{
            background: silver;
            box-shadow: inset -1px -1px #0a0a0a, inset 1px 1px #fff, inset -2px -2px grey, inset 2px 2px #dfdfdf;
            border: none;
            border-radius: 0;
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            padding: 6px 12px;
            min-width: 75px;
            min-height: 23px;
            outline: none;
        }}
        
        button:active {{
            box-shadow: inset -1px -1px #fff, inset 1px 1px #0a0a0a, inset -2px -2px #dfdfdf, inset 2px 2px grey;
            padding: 7px 11px 5px 13px;
        }}
        
        button:focus {{
            outline: 1px dotted #000;
            outline-offset: -4px;
        }}
        
        button:disabled {{
            color: #808080;
            text-shadow: 1px 1px 0 #fff;
        }}
        
        /* Form Elements */
        select, input[type="text"], input[type="email"], input[type="password"] {{
            background-color: #fff;
            box-shadow: inset -1px -1px #fff, inset 1px 1px grey, inset -2px -2px #dfdfdf, inset 2px 2px #0a0a0a;
            border: none;
            border-radius: 0;
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            padding: 3px 4px;
            height: 21px;
            -webkit-appearance: none;
            -moz-appearance: none;
            appearance: none;
        }}
        
        select {{
            padding-right: 32px;
            background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg width='16' height='17' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M15 0H0v16h1V1h14V0z' fill='%23DFDFDF'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M2 1H1v14h1V2h12V1H2z' fill='%23fff'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M16 17H0v-1h15V0h1v17z' fill='%23000'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M15 1h-1v14H1v1h14V1z' fill='gray'/%3E%3Cpath fill='silver' d='M2 2h12v13H2z'/%3E%3Cpath fill-rule='evenodd' clip-rule='evenodd' d='M11 6H4v1h1v1h1v1h1v1h1V9h1V8h1V7h1V6z' fill='%23000'/%3E%3C/svg%3E");
            background-position: top 2px right 2px;
            background-repeat: no-repeat;
        }}
        
        label {{
            display: inline-flex;
            align-items: center;
            margin-right: 8px;
        }}
        
        /* Field Row */
        .field-row {{
            display: flex;
            align-items: center;
            margin-bottom: 6px;
        }}
        
        .field-row > * + * {{
            margin-left: 6px;
        }}
        
        /* Desktop Layout */
        .desktop {{
            min-height: 100vh;
            position: relative;
            overflow: hidden;
            background: #008080;
        }}
        
        .desktop-icons {{
            position: absolute;
            top: 20px;
            left: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fill, 80px);
            gap: 20px;
            z-index: 10;
        }}
        
        .desktop-icon {{
            width: 64px;
            height: 80px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            padding: 4px;
            border: 1px solid transparent;
            user-select: none;
        }}
        
        .desktop-icon:hover {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px dotted #fff;
        }}
        
        .desktop-icon.selected {{
            background: rgba(0, 0, 128, 0.3);
            border: 1px dotted #fff;
        }}
        
        .desktop-icon-image {{
            width: 32px;
            height: 32px;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .desktop-icon-image img {{
            width: 32px;
            height: 32px;
            image-rendering: pixelated;
            image-rendering: -moz-crisp-edges;
            image-rendering: crisp-edges;
        }}
        
        .desktop-icon-label {{
            font-size: 10px;
            color: white;
            text-align: center;
            line-height: 1.2;
            text-shadow: 1px 1px 0px #000;
            max-width: 60px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .windows-container {{
            position: relative;
            width: 100%;
            height: 100vh;
        }}
        
        /* Window positioning */
        .window {{
            width: 500px;
            min-height: 200px;
            max-width: 90vw;
            display: none; /* Hidden by default */
        }}
        
        /* Data viewer window (larger) */
        .window:nth-child(3) {{
            width: 700px;
            min-height: 400px;
        }}
        
        /* Taskbar */
        .taskbar {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            height: 28px;
            background: #c0c0c0;
            border-top: 1px solid #ffffff;
            border-bottom: 1px solid #0a0a0a;
            box-shadow: inset 0 1px 0 #ffffff, inset 0 -1px 0 #0a0a0a;
            display: flex;
            align-items: center;
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            z-index: 1000;
        }}
        
        .start-button {{
            height: 22px;
            padding: 2px 4px 2px 2px;
            margin: 2px;
            background: #c0c0c0;
            border: 1px solid;
            border-color: #ffffff #0a0a0a #0a0a0a #ffffff;
            box-shadow: inset 1px 1px 0 #dfdfdf, inset -1px -1px 0 #808080;
            cursor: pointer;
            display: flex;
            align-items: center;
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            color: #000;
            font-weight: bold;
        }}
        
        .start-button:hover {{
            background: #dfdfdf;
        }}
        
        .start-button:active {{
            border-color: #0a0a0a #ffffff #ffffff #0a0a0a;
            box-shadow: inset -1px -1px 0 #dfdfdf, inset 1px 1px 0 #808080;
        }}
        
        .task-buttons {{
            flex: 1;
            display: flex;
            margin: 0 4px;
            gap: 2px;
        }}
        
        .task-button {{
            height: 22px;
            padding: 2px 8px;
            background: #c0c0c0;
            border: 1px solid;
            border-color: #ffffff #0a0a0a #0a0a0a #ffffff;
            box-shadow: inset 1px 1px 0 #dfdfdf, inset -1px -1px 0 #808080;
            cursor: pointer;
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            color: #000;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            min-width: 100px;
            max-width: 200px;
        }}
        
        .task-button:hover {{
            background: #dfdfdf;
        }}
        
        .task-button.active {{
            border-color: #0a0a0a #ffffff #ffffff #0a0a0a;
            box-shadow: inset -1px -1px 0 #dfdfdf, inset 1px 1px 0 #808080;
            background: #dfdfdf;
        }}
        
        .system-tray {{
            height: 22px;
            margin: 2px;
            padding: 2px 6px;
            background: #c0c0c0;
            border: 1px inset #c0c0c0;
            display: flex;
            align-items: center;
        }}
        
        .tray-clock {{
            font-family: "Pixelated MS Sans Serif", Arial;
            font-size: 11px;
            color: #000;
        }}
        
        /* Add padding to desktop to avoid overlap with taskbar */
        .desktop {{
            padding-bottom: 40px;
        }}
        
        /* Window Resize Handles */
        .resize-handle {{
            position: absolute;
            background: transparent;
        }}
        
        .resize-handle.n {{
            top: 0;
            left: 8px;
            right: 8px;
            height: 4px;
            cursor: n-resize;
        }}
        
        .resize-handle.s {{
            bottom: 0;
            left: 8px;
            right: 8px;
            height: 4px;
            cursor: s-resize;
        }}
        
        .resize-handle.e {{
            top: 8px;
            right: 0;
            bottom: 8px;
            width: 4px;
            cursor: e-resize;
        }}
        
        .resize-handle.w {{
            top: 8px;
            left: 0;
            bottom: 8px;
            width: 4px;
            cursor: w-resize;
        }}
        
        .resize-handle.ne {{
            top: 0;
            right: 0;
            width: 8px;
            height: 8px;
            cursor: ne-resize;
        }}
        
        .resize-handle.nw {{
            top: 0;
            left: 0;
            width: 8px;
            height: 8px;
            cursor: nw-resize;
        }}
        
        .resize-handle.se {{
            bottom: 0;
            right: 0;
            width: 8px;
            height: 8px;
            cursor: se-resize;
        }}
        
        .resize-handle.sw {{
            bottom: 0;
            left: 0;
            width: 8px;
            height: 8px;
            cursor: sw-resize;
        }}
        
        /* Visual resize indicator (optional subtle border on hover) */
        .window:hover .resize-handle {{
            background: rgba(0, 0, 0, 0.1);
        }}
    </style>
</head>
<body>
    <div class="desktop">
        <!-- Desktop Icons -->
        <div class="desktop-icons">
            <div class="desktop-icon" data-window="0">
                <div class="desktop-icon-image">
                    <img src="/icons/settings.png" alt="Settings" />
                </div>
                <div class="desktop-icon-label">Gmail Connection</div>
            </div>
            <div class="desktop-icon" data-window="1">
                <div class="desktop-icon-image">
                    <img src="/icons/mail.png" alt="Mail" />
                </div>
                <div class="desktop-icon-label">Email Sync</div>
            </div>
            <div class="desktop-icon" data-window="2">
                <div class="desktop-icon-image">
                    <img src="/icons/chart.png" alt="Chart" />
                </div>
                <div class="desktop-icon-label">Processing Data</div>
            </div>
            <div class="desktop-icon" data-action="reset">
                <div class="desktop-icon-image">
                    <img src="/icons/trash.png" alt="Trash" />
                </div>
                <div class="desktop-icon-label">Reset Database</div>
            </div>
        </div>
        
        <div class="windows-container">
            
            <!-- Gmail Connection Window -->
            <div class="window">
                <div class="title-bar">
                    <div class="title-bar-text">Gmail Connection</div>
                    <div class="title-bar-controls">
                        <button aria-label="Minimize"></button>
                        <button aria-label="Maximize"></button>
                        <button aria-label="Close"></button>
                    </div>
                </div>
                <div class="window-body">
                    {connections_html}
                </div>
            </div>
            
            <!-- Email Sync Window -->
            <div class="window">
                <div class="title-bar">
                    <div class="title-bar-text">Email Sync</div>
                    <div class="title-bar-controls">
                        <button aria-label="Minimize"></button>
                        <button aria-label="Maximize"></button>
                        <button aria-label="Close"></button>
                    </div>
                </div>
                <div class="window-body">
                    <div class="field-row">
                        <label for="emailCount">Number of emails:</label>
                        <select id="emailCount">
                            <option value="5">5</option>
                            <option value="30" selected>30</option>
                            <option value="100">100</option>
                            <option value="500">500</option>
                        </select>
                    </div>
                    <div class="field-row">
                        <label for="syncDirection">Sync direction:</label>
                        <select id="syncDirection">
                            <option value="recent" selected>Most recent emails</option>
                            <option value="older">Older emails (from last processed)</option>
                        </select>
                    </div>
                    <div class="field-row" style="margin-top: 12px;">
                        <button onclick="syncEmails()">Sync Emails</button>
                    </div>
                </div>
            </div>
            
            <!-- Fast Metadata Fetch Window (Testing) -->
            <div class="window" style="margin-top: 16px;">
                <div class="title-bar">
                    <div class="title-bar-text">📧 Fast Metadata Fetch (Testing)</div>
                    <div class="title-bar-controls">
                        <button aria-label="Minimize"></button>
                        <button aria-label="Maximize"></button>
                        <button aria-label="Close"></button>
                    </div>
                </div>
                <div class="window-body">
                    <p style="font-size: 11px; margin-bottom: 12px;">
                        <strong>Test fast email ingestion:</strong> Fetches email metadata only (subject, sender, date) without body content or LLM processing.
                        Expected ~10x speed improvement.
                    </p>
                    <div class="field-row">
                        <label for="metadataCount">Number of emails:</label>
                        <select id="metadataCount">
                            <option value="100">100 emails</option>
                            <option value="500">500 emails</option>
                            <option value="1000" selected>1,000 emails</option>
                            <option value="5000">5,000 emails</option>
                            <option value="10000">10,000 emails</option>
                        </select>
                    </div>
                    <div class="field-row" style="margin-top: 12px;">
                        <button onclick="fetchMetadataOnly()" id="metadataButton">🚀 Fetch Metadata Only</button>
                    </div>
                    <div id="metadataStatus" style="margin-top: 12px; font-size: 11px; color: #333;">
                        Ready to fetch metadata...
                    </div>
                </div>
            </div>
            
            <!-- Data Viewer Window -->
            <div class="window">
                <div class="title-bar">
                    <div class="title-bar-text">Processing Data</div>
                    <div class="title-bar-controls">
                        <button aria-label="Minimize"></button>
                        <button aria-label="Maximize"></button>
                        <button aria-label="Close"></button>
                    </div>
                </div>
                <div class="window-body" style="padding: 0;">
                    <!-- Tab Bar -->
                    <div style="background: #c0c0c0; border-bottom: 1px solid #808080; padding: 2px 8px;">
                        <menu role="tablist" style="margin: 0; padding: 0; list-style: none; display: flex; font-size: 11px;">
                            <button onclick="showTab('all-emails')" id="all-emails-tab" 
                                    aria-selected="true" style="padding: 4px 12px; margin-right: 2px; background: #c0c0c0; border: 1px solid; border-color: #fff #808080 #808080 #fff; border-bottom: none;">
                                All Emails
                            </button>
                            <button onclick="showTab('classified')" id="classified-tab"
                                    aria-selected="false" style="padding: 4px 12px; margin-right: 2px; background: #c0c0c0; border: 1px solid; border-color: #fff #808080 #808080 #fff;">
                                Classified Emails
                            </button>
                        </menu>
                    </div>
                    
                    <!-- Tab Content -->
                    <div style="padding: 8px;">
                        <!-- All Emails Tab -->
                        <div id="all-emails-content" class="tab-content">
                            <!-- Pagination Controls -->
                            <div id="all-emails-pagination" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; align-items: center; gap: 4px;">
                                    <button onclick="changePage('all-emails', -1)" id="all-emails-prev" style="min-width: 60px;">◄ Prev</button>
                                    <span id="all-emails-page-info" style="font-size: 11px; padding: 0 8px;">Page 1 of 1</span>
                                    <button onclick="changePage('all-emails', 1)" id="all-emails-next" style="min-width: 60px;">Next ►</button>
                                </div>
                                <div style="font-size: 10px; color: #666;">
                                    <span id="all-emails-total">0 emails total</span>
                                </div>
                            </div>
                            <!-- Scrollable Data Container -->
                            <div style="max-height: 300px; overflow-y: auto; border: 1px inset #c0c0c0; background: #fff;">
                                <div id="all-emails-data" style="font-size: 11px;">Loading...</div>
                            </div>
                        </div>
                        
                        <!-- Classified Emails Tab -->
                        <div id="classified-content" class="tab-content" style="display: none;">
                            <!-- Pagination Controls -->
                            <div id="classified-pagination" style="margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center;">
                                <div style="display: flex; align-items: center; gap: 4px;">
                                    <button onclick="changePage('classified', -1)" id="classified-prev" style="min-width: 60px;">◄ Prev</button>
                                    <span id="classified-page-info" style="font-size: 11px; padding: 0 8px;">Page 1 of 1</span>
                                    <button onclick="changePage('classified', 1)" id="classified-next" style="min-width: 60px;">Next ►</button>
                                </div>
                                <div style="font-size: 10px; color: #666;">
                                    <span id="classified-total">0 emails total</span>
                                </div>
                            </div>
                            <!-- Scrollable Data Container -->
                            <div style="max-height: 300px; overflow-y: auto; border: 1px inset #c0c0c0; background: #fff;">
                                <div id="classified-data" style="font-size: 11px;">Loading...</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
        </div>
    </div>
        
    <!-- Taskbar -->
    <div class="taskbar">
        <button class="start-button">
            <img src="/icons/settings.png" alt="Start" style="width: 16px; height: 16px; margin-right: 4px;" />
            Start
        </button>
        <div class="task-buttons" id="task-buttons">
            <!-- Task buttons will be dynamically added here -->
        </div>
        <div class="system-tray">
            <div class="tray-clock" id="tray-clock">12:00 PM</div>
        </div>
    </div>
        
        {get_javascript()}
</body>
</html>
"""

def get_javascript():
    """JavaScript for window management and UI interactions"""
    return """
        <script>
            // Window Management System
            class WindowManager {
                constructor() {
                    this.windows = new Map();
                    this.zIndex = 1000;
                    this.activeWindow = null;
                    this.initializeWindows();
                    this.initializeTaskbar();
                }
                
                initializeWindows() {
                    const windows = document.querySelectorAll('.window');
                    windows.forEach((window, index) => {
                        const id = `window-${index}`;
                        window.id = id;
                        window.style.position = 'absolute';
                        window.style.zIndex = this.zIndex + index;
                        
                        // Set initial positions (staggered)
                        window.style.left = `${50 + (index * 30)}px`;
                        window.style.top = `${50 + (index * 40)}px`;
                        
                        // Store original dimensions for restore
                        const rect = window.getBoundingClientRect();
                        
                        this.windows.set(id, {
                            element: window,
                            isDragging: false,
                            startX: 0,
                            startY: 0,
                            initialX: 0,
                            initialY: 0,
                            isMinimized: false,
                            isMaximized: false,
                            originalWidth: window.style.width || `${rect.width}px`,
                            originalHeight: window.style.height || `${rect.height}px`,
                            originalLeft: `${50 + (index * 30)}px`,
                            originalTop: `${50 + (index * 40)}px`
                        });
                        
                        this.makeDraggable(window);
                        this.addWindowControls(window);
                        this.addResizeHandles(window);
                    });
                }
                
                makeDraggable(windowElement) {
                    const titleBar = windowElement.querySelector('.title-bar');
                    const windowData = this.windows.get(windowElement.id);
                    
                    titleBar.style.cursor = 'move';
                    titleBar.style.userSelect = 'none';
                    
                    // Mouse down on title bar
                    titleBar.addEventListener('mousedown', (e) => {
                        // Don't drag if clicking on window controls
                        if (e.target.closest('.title-bar-controls')) return;
                        
                        this.startDrag(windowElement, e);
                        e.preventDefault();
                    });
                    
                    // Bring window to front when clicked anywhere
                    windowElement.addEventListener('mousedown', () => {
                        this.bringToFront(windowElement);
                    });
                }
                
                startDrag(windowElement, e) {
                    const windowData = this.windows.get(windowElement.id);
                    const rect = windowElement.getBoundingClientRect();
                    
                    windowData.isDragging = true;
                    windowData.startX = e.clientX - rect.left;
                    windowData.startY = e.clientY - rect.top;
                    windowData.initialX = rect.left;
                    windowData.initialY = rect.top;
                    
                    this.bringToFront(windowElement);
                    
                    // Add global mouse move and up listeners
                    document.addEventListener('mousemove', this.dragWindow.bind(this, windowElement));
                    document.addEventListener('mouseup', this.stopDrag.bind(this, windowElement));
                    
                    // Prevent text selection during drag
                    document.body.style.userSelect = 'none';
                }
                
                dragWindow(windowElement, e) {
                    const windowData = this.windows.get(windowElement.id);
                    if (!windowData.isDragging) return;
                    
                    const newX = e.clientX - windowData.startX;
                    const newY = e.clientY - windowData.startY;
                    
                    // Constrain to viewport
                    const maxX = window.innerWidth - windowElement.offsetWidth;
                    const maxY = window.innerHeight - windowElement.offsetHeight;
                    
                    const constrainedX = Math.max(0, Math.min(newX, maxX));
                    const constrainedY = Math.max(0, Math.min(newY, maxY));
                    
                    windowElement.style.left = `${constrainedX}px`;
                    windowElement.style.top = `${constrainedY}px`;
                }
                
                stopDrag(windowElement, e) {
                    const windowData = this.windows.get(windowElement.id);
                    windowData.isDragging = false;
                    
                    // Remove global listeners
                    document.removeEventListener('mousemove', this.dragWindow.bind(this, windowElement));
                    document.removeEventListener('mouseup', this.stopDrag.bind(this, windowElement));
                    
                    // Re-enable text selection
                    document.body.style.userSelect = '';
                }
                
                bringToFront(windowElement) {
                    if (this.activeWindow === windowElement) return;
                    
                    this.zIndex += 1;
                    windowElement.style.zIndex = this.zIndex;
                    this.activeWindow = windowElement;
                    
                    // Update title bar appearance for active window
                    this.updateWindowAppearance();
                }
                
                updateWindowAppearance() {
                    // Reset all title bars to inactive
                    document.querySelectorAll('.title-bar').forEach(titleBar => {
                        titleBar.style.background = 'linear-gradient(90deg, #808080, #c0c0c0)';
                    });
                    
                    // Make active window title bar blue
                    if (this.activeWindow) {
                        const activeTitleBar = this.activeWindow.querySelector('.title-bar');
                        activeTitleBar.style.background = 'linear-gradient(90deg, #000080, #1084d0)';
                    }
                }
                
                addWindowControls(windowElement) {
                    const controls = windowElement.querySelector('.title-bar-controls');
                    const buttons = controls.querySelectorAll('button');
                    
                    // Clear existing button content and add proper icons
                    buttons[0].innerHTML = '_';  // Minimize
                    buttons[1].innerHTML = '□';  // Maximize/Restore
                    buttons[2].innerHTML = '×';  // Close
                    
                    // Add click handlers
                    buttons[0].addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.minimizeWindow(windowElement);
                    });
                    
                    buttons[1].addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.toggleMaximize(windowElement);
                    });
                    
                    buttons[2].addEventListener('click', (e) => {
                        e.stopPropagation();
                        this.closeWindow(windowElement);
                    });
                }
                
                minimizeWindow(windowElement) {
                    const windowData = this.windows.get(windowElement.id);
                    
                    if (windowData.isMinimized) {
                        // Restore window
                        windowElement.style.display = 'block';
                        windowData.isMinimized = false;
                        this.bringToFront(windowElement);
                    } else {
                        // Minimize window
                        windowElement.style.display = 'none';
                        windowData.isMinimized = true;
                        
                        // If this was the active window, find next visible window
                        if (this.activeWindow === windowElement) {
                            this.activeWindow = null;
                            const visibleWindows = Array.from(this.windows.values())
                                .filter(w => !w.isMinimized && w.element !== windowElement);
                            if (visibleWindows.length > 0) {
                                this.bringToFront(visibleWindows[visibleWindows.length - 1].element);
                            }
                        }
                    }
                    
                    // Update taskbar button
                    this.updateTaskButton(windowElement.id);
                }
                
                toggleMaximize(windowElement) {
                    const windowData = this.windows.get(windowElement.id);
                    
                    if (windowData.isMaximized) {
                        // Restore window
                        windowElement.style.width = windowData.originalWidth;
                        windowElement.style.height = windowData.originalHeight;
                        windowElement.style.left = windowData.originalLeft;
                        windowElement.style.top = windowData.originalTop;
                        windowData.isMaximized = false;
                        
                        // Update button icon
                        const maximizeBtn = windowElement.querySelector('.title-bar-controls button:nth-child(2)');
                        maximizeBtn.innerHTML = '□';
                    } else {
                        // Store current position before maximizing
                        windowData.originalWidth = windowElement.style.width;
                        windowData.originalHeight = windowElement.style.height;
                        windowData.originalLeft = windowElement.style.left;
                        windowData.originalTop = windowElement.style.top;
                        
                        // Maximize window
                        windowElement.style.width = '100vw';
                        windowElement.style.height = '100vh';
                        windowElement.style.left = '0px';
                        windowElement.style.top = '0px';
                        windowData.isMaximized = true;
                        
                        // Update button icon
                        const maximizeBtn = windowElement.querySelector('.title-bar-controls button:nth-child(2)');
                        maximizeBtn.innerHTML = '❐';
                    }
                    
                    this.bringToFront(windowElement);
                }
                
                closeWindow(windowElement) {
                    const windowData = this.windows.get(windowElement.id);
                    
                    // Hide window with fade effect
                    windowElement.style.opacity = '0';
                    windowElement.style.transition = 'opacity 0.2s ease';
                    
                    setTimeout(() => {
                        windowElement.style.display = 'none';
                        windowElement.style.opacity = '1';
                        windowElement.style.transition = '';
                        
                        // If this was the active window, find next visible window
                        if (this.activeWindow === windowElement) {
                            this.activeWindow = null;
                            const visibleWindows = Array.from(this.windows.values())
                                .filter(w => w.element.style.display !== 'none' && w.element !== windowElement);
                            if (visibleWindows.length > 0) {
                                this.bringToFront(visibleWindows[visibleWindows.length - 1].element);
                            }
                        }
                    }, 200);
                }
                
                // Method to reopen a closed window
                openWindow(windowElement) {
                    const windowData = this.windows.get(windowElement.id);
                    windowElement.style.display = 'block';
                    windowData.isMinimized = false;
                    this.bringToFront(windowElement);
                    this.updateTaskButton(windowElement.id);
                }
                
                // Taskbar functionality
                initializeTaskbar() {
                    this.updateClock();
                    setInterval(() => this.updateClock(), 1000);
                }
                
                updateClock() {
                    const now = new Date();
                    const timeString = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                    const clockElement = document.getElementById('tray-clock');
                    if (clockElement) {
                        clockElement.textContent = timeString;
                    }
                }
                
                createTaskButton(windowId, title) {
                    const taskButtons = document.getElementById('task-buttons');
                    const button = document.createElement('button');
                    button.className = 'task-button';
                    button.id = `task-${windowId}`;
                    button.textContent = title;
                    button.addEventListener('click', () => {
                        this.restoreFromTaskbar(windowId);
                    });
                    taskButtons.appendChild(button);
                }
                
                removeTaskButton(windowId) {
                    const button = document.getElementById(`task-${windowId}`);
                    if (button) {
                        button.remove();
                    }
                }
                
                updateTaskButton(windowId) {
                    const button = document.getElementById(`task-${windowId}`);
                    const windowData = this.windows.get(windowId);
                    
                    if (button && windowData) {
                        if (windowData.isMinimized) {
                            button.classList.remove('active');
                        } else {
                            button.classList.add('active');
                        }
                    }
                }
                
                restoreFromTaskbar(windowId) {
                    const windowData = this.windows.get(windowId);
                    if (windowData) {
                        if (windowData.element.style.display === 'none') {
                            this.openWindow(windowData.element);
                        } else if (windowData.isMinimized) {
                            this.minimizeWindow(windowData.element); // This will restore it
                        } else {
                            this.bringToFront(windowData.element);
                        }
                    }
                }
            }
            
            // Initialize window manager when page loads
            let windowManager;
            document.addEventListener('DOMContentLoaded', () => {
                windowManager = new WindowManager();
                
                // Desktop icon click handlers
                document.querySelectorAll('.desktop-icon').forEach(icon => {
                    icon.addEventListener('click', () => {
                        const windowIndex = icon.getAttribute('data-window');
                        const action = icon.getAttribute('data-action');
                        
                        if (action === 'reset') {
                            if (confirm('Are you sure you want to reset the database? This will delete all data.')) {
                                window.location.href = '/reset';
                            }
                        } else if (windowIndex !== null) {
                            const windowId = `window-${windowIndex}`;
                            const windowData = windowManager.windows.get(windowId);
                            if (windowData) {
                                windowManager.openWindow(windowData.element);
                            }
                        }
                    });
                });
                
                // Load initial data
                loadAllEmails();
                loadClassifiedEmails();
            });
            
            // Tab functionality
            function showTab(tabName) {
                // Hide all tab contents
                document.querySelectorAll('.tab-content').forEach(content => {
                    content.style.display = 'none';
                });
                
                // Reset all tab buttons
                document.querySelectorAll('[role="tablist"] button').forEach(button => {
                    button.setAttribute('aria-selected', 'false');
                    button.style.borderBottom = '1px solid #808080';
                });
                
                // Show selected tab content
                const selectedContent = document.getElementById(`${tabName}-content`);
                if (selectedContent) {
                    selectedContent.style.display = 'block';
                }
                
                // Update selected tab button
                const selectedTab = document.getElementById(`${tabName}-tab`);
                if (selectedTab) {
                    selectedTab.setAttribute('aria-selected', 'true');
                    selectedTab.style.borderBottom = 'none';
                }
                
                // Load data for the selected tab
                if (tabName === 'all-emails') {
                    loadAllEmails();
                } else if (tabName === 'classified') {
                    loadClassifiedEmails();
                }
            }
            
            // Pagination state
            const paginationState = {
                'all-emails': { page: 1, limit: 10 },
                'classified': { page: 1, limit: 10 }
            };
            
            function changePage(tabName, direction) {
                const state = paginationState[tabName];
                const newPage = state.page + direction;
                
                if (newPage < 1) return; // Don't go below page 1
                
                state.page = newPage;
                
                if (tabName === 'all-emails') {
                    loadAllEmails();
                } else if (tabName === 'classified') {
                    loadClassifiedEmails();
                }
            }
            
            function loadAllEmails() {
                const state = paginationState['all-emails'];
                const offset = (state.page - 1) * state.limit;
                
                fetch(`/api/emails?classified=false&limit=${state.limit}&offset=${offset}`)
                    .then(response => response.json())
                    .then(data => {
                        const container = document.getElementById('all-emails-data');
                        if (data.emails && data.emails.length > 0) {
                            container.innerHTML = `
                                <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                                    <thead style="background: #e0e0e0;">
                                        <tr>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 30%;">Subject</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 25%;">Sender</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 15%;">Date</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: center; width: 15%;">Subscription</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: center; width: 15%;">Confidence</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.emails.map(email => `
                                            <tr style="border-bottom: 1px solid #e0e0e0;">
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; word-break: break-word;">${email.subject || 'No Subject'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; word-break: break-word;">${email.sender || 'Unknown'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px;">${email.received_at ? new Date(email.received_at).toLocaleDateString() : 'Unknown'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; text-align: center;">${email.is_subscription ? 'Yes' : 'No'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; text-align: center;">${email.confidence_score ? Math.round(email.confidence_score * 100) + '%' : 'N/A'}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            `;
                        } else {
                            container.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">No emails found. Try syncing some emails first.</p>';
                        }
                        
                        // Update pagination controls
                        updatePaginationControls('all-emails', data.total);
                    })
                    .catch(error => {
                        console.error('Error loading all emails:', error);
                        document.getElementById('all-emails-data').innerHTML = '<p style="padding: 20px; text-align: center; color: red;">Error loading emails</p>';
                    });
            }
            
            function loadClassifiedEmails() {
                const state = paginationState['classified'];
                const offset = (state.page - 1) * state.limit;
                
                fetch(`/api/emails?classified=true&limit=${state.limit}&offset=${offset}`)
                    .then(response => response.json())
                    .then(data => {
                        const container = document.getElementById('classified-data');
                        if (data.emails && data.emails.length > 0) {
                            container.innerHTML = `
                                <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                                    <thead style="background: #e0e0e0;">
                                        <tr>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 30%;">Subject</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 25%;">Sender</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 15%;">Vendor</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: center; width: 15%;">Confidence</th>
                                            <th style="border: 1px solid #808080; padding: 4px; text-align: left; width: 15%;">Date</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${data.emails.map(email => `
                                            <tr style="border-bottom: 1px solid #e0e0e0;">
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; word-break: break-word;">${email.subject || 'No Subject'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; word-break: break-word;">${email.sender || 'Unknown'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px;">${email.vendor || 'Unknown'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px; text-align: center;">${email.confidence_score ? Math.round(email.confidence_score * 100) + '%' : 'N/A'}</td>
                                                <td style="border: 1px solid #e0e0e0; padding: 4px;">${email.received_at ? new Date(email.received_at).toLocaleDateString() : 'Unknown'}</td>
                                            </tr>
                                        `).join('')}
                                    </tbody>
                                </table>
                            `;
                        } else {
                            container.innerHTML = '<p style="padding: 20px; text-align: center; color: #666;">No classified emails found. Try syncing some emails first.</p>';
                        }
                        
                        // Update pagination controls
                        updatePaginationControls('classified', data.total);
                    })
                    .catch(error => {
                        console.error('Error loading classified emails:', error);
                        document.getElementById('classified-data').innerHTML = '<p style="padding: 20px; text-align: center; color: red;">Error loading emails</p>';
                    });
            }
            
            function updatePaginationControls(tabName, total) {
                const state = paginationState[tabName];
                const totalPages = Math.ceil(total / state.limit);
                
                // Update page info
                document.getElementById(`${tabName}-page-info`).textContent = `Page ${state.page} of ${totalPages}`;
                document.getElementById(`${tabName}-total`).textContent = `${total} emails total`;
                
                // Update button states
                document.getElementById(`${tabName}-prev`).disabled = state.page <= 1;
                document.getElementById(`${tabName}-next`).disabled = state.page >= totalPages;
            }
            
            // Email sync functionality
            function syncEmails() {
                const emailCount = document.getElementById('emailCount').value;
                const syncDirection = document.getElementById('syncDirection').value;
                
                const button = document.querySelector('button[onclick="syncEmails()"]');
                const originalText = button.textContent;
                button.disabled = true;
                button.textContent = 'Syncing...';
                
                fetch(`/sync?count=${emailCount}&direction=${syncDirection}`, {
                    method: 'GET'
                })
                .then(response => response.text())
                .then(result => {
                    alert('Sync completed! Check the Processing Data window for results.');
                    // Refresh data
                    loadAllEmails();
                    loadClassifiedEmails();
                })
                .catch(error => {
                    console.error('Sync error:', error);
                    alert('Sync failed. Check console for details.');
                })
                .finally(() => {
                    button.disabled = false;
                    button.textContent = originalText;
                });
            }
            
            // Fast metadata fetch functionality
            function fetchMetadataOnly() {
                const metadataCount = document.getElementById('metadataCount').value;
                const button = document.getElementById('metadataButton');
                const status = document.getElementById('metadataStatus');
                
                const originalText = button.textContent;
                button.disabled = true;
                button.textContent = 'Fetching...';
                status.textContent = 'Fetching metadata from Gmail...';
                
                fetch(`/fetch-metadata?count=${metadataCount}`, {
                    method: 'GET'
                })
                .then(response => response.json())
                .then(result => {
                    if (result.error) {
                        status.textContent = `Error: ${result.error}`;
                        status.style.color = 'red';
                    } else {
                        status.textContent = `✓ Success: ${result.fetched} emails fetched, ${result.stored} new emails stored in ${result.time}s`;
                        status.style.color = 'green';
                        // Refresh data
                        loadAllEmails();
                    }
                })
                .catch(error => {
                    console.error('Metadata fetch error:', error);
                    status.textContent = 'Error: Failed to fetch metadata';
                    status.style.color = 'red';
                })
                .finally(() => {
                    button.disabled = false;
                    button.textContent = originalText;
                });
            }
        </script>
    """

def render_connections(connections):
    """Render Gmail connections section"""
    if not connections:
        return """
            <p>No Gmail connections found.</p>
            <button onclick="window.location.href='/auth/gmail'">Connect Gmail Account</button>
        """
    
    connections_html = ""
    for conn in connections:
        status = "✅ Active" if conn['is_active'] else "❌ Inactive"
        last_sync = conn['last_sync_at'] if conn['last_sync_at'] else "Never"
        connections_html += f"""
            <div style="margin-bottom: 12px; padding: 8px; border: 1px inset #c0c0c0; background: #f0f0f0;">
                <div><strong>Email:</strong> {conn['email']}</div>
                <div><strong>Status:</strong> {status}</div>
                <div><strong>Last Sync:</strong> {last_sync}</div>
            </div>
        """
    
    connections_html += """
        <button onclick="window.location.href='/auth/gmail'" style="margin-top: 8px;">Add Another Account</button>
    """
    
    return connections_html