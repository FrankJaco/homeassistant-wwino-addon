# Wonderful Wino
A personal wine inventory system that can be exposed to the AI/Voice assistant for real-time wine-pairing suggestions and general wine info.

### Table of Contents

 - <a href="#about" target="_self">About Wonderful Wino</a>
 - <a href="#installing-the-wonderful-wino-add-on" target="_self">Installation of the Add-on</a>
 - <a href="#wonderful-wino-add-on-configuration" target="_self">Add-on Configuration</a>
 - <a href="#home-assistant-configuration-for-wonderful-wino" target="_self">Home Assistant Configuration for Wonderful Wino</a>
   - <a href="#local-todo-list" target="_self">Local To Do list</a>
   - <a href="#home-assistant-configurationyaml" target="_self">configuration.yaml addition</a>
   - <a href="#create-four-home-assistant-helpers" target="_self">Helpers</a>
   - <a href="#home-assistant-automation" target="_self">Automation</a>
   - <a href="#home-assistant-dashboard" target="_self">Dashboard</a>
   - <a href="#determining-wonderful-wino-ingress-url" target="_self">Ingress URL for WW GUI</a>
   - <a href="#voice-assistant-ai-prompts" target="_self">Voice Assistant AI Prompts</a>
 - <a href="#quick-visual-guide-to-using-wonderful-wino" target="_self">Quick Visual Guide to using Wonderful Wino</a>
   - <a href="#manually-via-wonderful-wino-gui" target="_self">Adding Wine Manually</a>
   - <a href="#vivino-assisted-via-wonderful-wino-gui" target="_self">Adding Wine Via Vivino URL</a>
   - <a href="#other-tools-for-adding-wine-to-your-database" target="_self">Other Tools for Adding Wine to your DB</a>
     - <a href="#wonderful-wino-chrome-browser-extension" target="_self">Chrome Browser Extension</a>
     - <a href="#wonderful-wino-android-helper-app" target="_self">Android Helper App</a>
   - <a href="#inventory-display-and-filtering-controls" target="_self">Inventory Display Filtering & Sorting</a>
   - <a href="#wine-inventory-display-panel" target="_self">Wine Inventory Display Panel</a>
     - <a href="#actions" target="_self">Actions</a>
     - <a href="#wine-details-and-metrics" target="_self">Wine Details and Metrics</a>
     - <a href="#thumbnail-image" target="_self">Thumbnail Image</a>
       - <a href="#thumbnail-image" target="_self">Tasting Notes</a>
       - <a href="#thumbnail-image" target="_self">Consumption Log</a>
   - <a href="#accessing-settings-and-screen-mode" target="_self">Accessing Settings and Screen Mode</a>
   - <a href="#accessing-settings-and-screen-mode" target="_self">Settings and Maintenance</a>
     - <a href="#setting-cost-tiers" target="_self">Setting Cost Tiers</a>
     - <a href="#maintenance-tools" target="_self">Database Backup and Recovery</a>
     - <a href="#maintenance-tools" target="_self">Maintenance Tools</a>
   - <a href="#accessing-your-wine-from-within-home-assistant" target="_self">Accessing Your Wine from within Home Assistant</a>
     - <a href="#todo-list-controls" target="_self">ToDo List Controls</a>
     - <a href="#todo-list-entry-details" target="_self">ToDo List Entry Details</a>
 - <a href="#how-did-wonderful-wino-come-about" target="_self">How did Wonderful Wino come about?</a>

<a name="about"></a>
## About

The Wonderful Wino add-on provides a user-friendly interface to manage your wine collection within Home Assistant. It can utilize the Local ToDo list integration to maintain a copy of your wine collection making it accessible to your Home Assistant's AI/Voice assistant. 

![mainview](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/gui.png)

We know many "WWinos" out there are familiar with the wwondeful [Vivino](https://www.vivino.com/) website and app.  If you’re not, we highly recommend checking them out. While a Vivino account isn’t required for WW, it’s a fantastic tool that can greatly enhance your wine experience. Wonderful Wino accesses the public areas of the Vivino site to obtain the basic facts about your wine streamlining the task of adding them to your inventory.

Exposing your wine collection to Home Assistant's Voice Assistant (with AI) via the Local ToDo List integration opens up limitless possibilities. When properly configured, your wine facts are just a question away. *Hey Nabu... How many Cabs do I have? What is my oldest vintage? Which wine is rated the highest?* But it can be  so much more than that. It is like having a personal sommelier available at your every whim. (OK, you got to open the bottle yourself!). 

![AI pairing](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ai.png)

The ToDo list itself provides on-the-go convenience. The user can see his wine along with essential wine facts in a compact form. Also the user can perform a subset of wine inventory tasks such as informing Wonderful Wino's backend that you consumed a bottle (which removes it from inventory and permits you to optionally rate the wine you just drank). 

![ToDo](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/todo.png)

Beyond the Wonderful Wino Add-on and its GUI, there are currently two additional input tools to help streamline adding wine to your inventory after a visit to your favorite wine merchant:  For those users of the Chrome Browser, there is the [Wonderful Wino Chrome Extension](https://github.com/FrankJaco/wwino-chrome-extension). And for Android phone users who utilize the Vivino App there is the [Wonderful Wino Helper App](https://github.com/FrankJaco/wwino-android-helper). 

![CBE](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/cbe.png)  ![AHA](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/aha.png)

<a name="installing-the-wonderful-wino-add-on"></a>
# Installing the Wonderful Wino Add-on:

**Prerequisites:**
You must be running a version of Home Assistant that includes the Supervisor panel. (e.g. Home Assistant OS) and have enabled "Advanced Mode" in your Home Assistant user profile.


**Installation Steps:**
Adding a custom add-on repository is a fairly straightforward process. Please follow these steps carefully.

1.  **Navigate to the Add-on Store**
    * Open your Home Assistant frontend.
    * In the left-hand menu, click on **Settings**.
    * From the Settings menu, select **Add-ons**.
    * Click the blue **Add-On Store** button in the bottom right corner.

2.  **Add the Custom Repository**
    * Click the **three-dots menu** in the top right corner.
    * Select **Repositories**.
    * Paste the repository URL `https://github.com/FrankJaco/homeassistant-wwino-addon` and click **Add**.
    * Click **Close**.
3.  **Install the Wonderful Wino Add-on**
    * After adding the repository, you may need to refresh the page for the new addon to appear by pressing `Ctrl + R` (or `Cmd + R` on a Mac).
    * Scroll through the Add-on Store and locate the section titled **Wonderful Wino Add-on Repository**.
    * Click on the **Wonderful Wino** add-on card to open its information page.
    * Click the blue **Install** button and wait for the installation process to complete. This may take a few minutes.

<a name="wonderful-wino-add-on-configuration"></a>
## Wonderful Wino Add-on Configuration

![conf](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/conf.png)

**Creating a Home Assistant Long Lived Token: for Wonderful Wino** 1. Click on your **User Account** (bottom of the Home Assistant sidebar on the left).
2. Select the **Security tab** at the top of the screen and scroll to its bottom.
3. In the **Long-lived access tokens** section and click **Create Token**.
4. Name it **WWino** (or anything else you want) and click **OK**
5. **Copy and paste** it to the Configuration tab's `HA_LONG_LIVED_TOKEN` textbox.

Click **Save** in lower right corner of this panel. 

***This completes the Add-on configuration. We are now ready to start the add-on**.*


### Starting Wonderful Wino for the First Time

 - Go to the **Info tab**, and select your desired startup options.
   "Add to Sidebar" is recommended at least at first.
 - Click **Start**.

*You may want to check the log (by going into the **Log tab**) to ensure a proper first start. It should look something like this...*

    Starting Wonderful Wino backend...
    2025-10-03 12:21:09,021 - app.db - INFO - Database initialized at /share/wwino/wine_inventory.db
    2025-10-03 12:21:09,021 - __main__ - INFO - Starting Wonderful Wino on port 5000 with log level INFO
    ---> NOTE: The following 'WARNING' is a standard benign message from the internal web server.
    ---> It is normal and expected for a Home Assistant add-on and can be safely ignored.
     * Serving Flask app 'main'
     * Debug mode: off
    2025-10-03 12:21:09,023 - werkzeug - INFO - WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
     * Running on all addresses (0.0.0.0)
     * Running on http://127.0.0.1:5000
     * Running on http://172.30.33.13:5000
    2025-10-03 12:21:09,024 - werkzeug - INFO - Press CTRL+C to quit
     * Running on all addresses (0.0.0.0)
     * Running on http://127.0.0.1:5000
     * Running on http://172.30.33.13:5000
    2025-10-03 12:21:09,024 - werkzeug - INFO - Press CTRL+C to quit

***If everything checks out, congratulations, Wonderful Wino is up and running and ready for you to add your wine! You could stop right here and use Wonderful Wino as is via its GUI. But to really make Wonderful Wino truly wwonderful, we need to configure Home Assistant a wwee bit more.***


<a name="home-assistant-configuration-for-wonderful-wino"></a>
# Home Assistant Configuration for Wonderful Wino

To get the most out of Wonderful Wino, the [Local ToDo list integration](https://www.home-assistant.io/integrations/local_todo/), and a functioning [Home Assistant Voice Assistant](https://www.home-assistant.io/voice_control/) enhanced with Ai are required. (fyi, I personally use the [Google Gemini](https://www.home-assistant.io/integrations/google_generative_ai_conversation/) integration and it does a nice job.) This section will tie these various parts together.

<a name="local-todo-list"></a>
### Local ToDo list:

If you have not done so already, install the [Local ToDo list integration](https://www.home-assistant.io/integrations/local_todo/)  now.

 Make a ToDo list called **My Wine** `todo.my_wine`

(Technically you could call it anything you want, but all the included documentation and yaml etc. are built around that assumption. I recommend starting with "My Wine" first and getting everything up and running before "crossing the beams".)


<a name="home-assistant-configurationyaml"></a>
### Home Assistant configuration.yaml:
For connectivity between Wonderful Wino and Home Assistant / Local ToDo list a small addition to the configuration.yaml file is required.  You can use the [FileEditor or VSCode add-ons](https://www.home-assistant.io/common-tasks/os/)  for this task.

    # Wonderful-Wino Stuff
    rest_command:
      wine_consumed_webhook:
        url: "http://<your HomeAssistant IP>:5000/api/consume-wine"
        method: POST
        content_type: "application/json"
        payload: >
          {
            "item": "{{ item }}",
            "timestamp": "{{ now().isoformat() }}"
            {% if rating | float(0) > 0 %}
            ,"rating": {{ rating }}
            {% endif %}
          }

**Don't forget** to put in your **Home Assistant's IP address** where indicated!
*Practice safe "yamling" by checking the configuration in **Developer Tools**, then ***restart Home Assistant***.*

<a name="create-four-home-assistant-helpers"></a>
### Create Four Home Assistant Helpers:
*All four Helpers can be created via the Home Assistant GUI.*

Note that each helper is of a different type (**Input_Text** - **Input_Number** - **Input_Select** - **Input_Boolean**) 

**Last Consumed Wine** (**Input_Text** Helper)

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/lwc.png)

**Taste Rating** (**Input_Number** Helper)

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/trh.png)

**ToDo List Sort Order** (**Input_Select** Helper)

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/tdlso.png)


**Show Ratings Card** (**Input_Boolean** Helper)

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/src.png)


<a name="home-assistant-automation"></a>
### Home Assistant Automation:
*Now with the 4 Helpers created, we can create our one required automation.*

The purpose of the automation is for the ToDo list functionality in where the user can "complete / consume" a wine via the ToDo list. The automation will trap that event, provide the user the option of rating the consumed wine, then send the data to the back end to decrement inventory and rate the wine.


    alias: "Wonderful-Wino: Prep for Wine Rating, then consume via ToDo"
    description: On consumption of a wine, it prepares the UI for an optional rating.
    triggers:
      - entity_id: todo.my_wine
        trigger: state
    conditions:
      - condition: template
        value_template: >-
          {{ trigger.from_state is not none and trigger.to_state is not none and
          trigger.from_state.state is not none and trigger.to_state.state is not
          none and trigger.from_state.state | int(-1) is number and
          trigger.to_state.state | int(-1) is number }}
      - condition: template
        value_template: >-
          {{ trigger.to_state.state | int(-1) < trigger.from_state.state | int(-1)
          }}
    actions:
      - target:
          entity_id: "{{ list_entity }}"
        data:
          status: completed
        response_variable: completed_wines
        action: todo.get_items
      - repeat:
          for_each: "{{ completed_wines[list_entity]['items'] }}"
          sequence:
            - data:
                name: Wonderful Wino
                message: "🍷 Consumed: {{ repeat.item.summary }}"
              action: logbook.log
            - target:
                entity_id: input_text.last_consumed_wine
              data:
                value: "{{ repeat.item.summary }}"
              action: input_text.set_value
            - target:
                entity_id: input_number.taste_rating
              data:
                value: 0
              action: input_number.set_value
            - target:
                entity_id:
                  - input_boolean.show_rating_card
              action: input_boolean.turn_on
              data: {}
            - target:
                entity_id: "{{ list_entity }}"
              data:
                item: "{{ repeat.item.uid }}"
              action: todo.remove_item
    mode: queued
    variables:
      list_entity: todo.my_wine

<a name="home-assistant-dashboard"></a>
### Home Assistant "Subview" Dashboard
This subview dashboard provides these functions:

 1. Sortable Wine List in a ToDo list card
 2. Direct access to the full Wonderful Wino GUI
 3. The Wine Rating interface (that is used by the automation above)
 4. Badge with the total of "Unique Wines" on hand.  (ignores the quantity of each)

The Dashboard subview yaml is below. I suggest that you start with it - Make a new Dashboard Subview accessible from one of your current boards then paste the code into it. From there you can adjust it as needed. Once you see how they operate, you certainly can move the cards to anywhere you would like.

Take particular note of the **INGRESS** lines in the yaml as you will need to edit them if you want to use the function. It permits direct access to the main Wonderful Wino GUI by tapping the Header of the ToDo list. I will provide info on how to find your **INGRESS SLUG** below the Dashboard yaml. You will need to replace the 8 X's with your specific 8 characters to make the "navigate to GUI" feature work.

    type: sections
    max_columns: 1
    title: Vino
    path: vino
    icon: mdi:glass-wine
    subview: true
    dense_section_placement: true
    sections:
      - type: grid
        max_columns: 1
        cards:
          - type: entities
            title: Rate Your Last Wine? 🍷
            show_header_toggle: false
            entities:
              - entity: input_text.last_consumed_wine
                name: Wine
              - entity: input_number.taste_rating
                name: Rating
              - type: button
                name: Submit Rating
                icon: mdi:send
                action_name: Submit
                tap_action:
                  action: call-service
                  service: script.wonderful_wino_submit_taste_rating
          - type: markdown
            content: >-
              _Submitting the wine with a 0 star rating consumes the wine without
              rating it. Any other value (0.5 - 5.0 stars) updates the wine's
              rating._
        visibility:
          - condition: state
            entity: input_boolean.show_rating_card
            state: "on"
      - type: grid
        cards:
          - type: heading
            heading_style: subtitle
            heading: Wine List
            icon: mdi:glass-wine
            badges:
              - type: entity
                show_state: true
                show_icon: true
                entity: input_select.todo_list_sort_order
                name: A-Z
                icon: mdi:sort-alphabetical-ascending
                state_content: name
                color: lime
                tap_action:
                  action: perform-action
                  perform_action: input_select.select_option
                  target:
                    entity_id: input_select.todo_list_sort_order
                  data:
                    option: A to Z
              - type: entity
                show_state: true
                show_icon: true
                entity: input_select.todo_list_sort_order
                color: deep-orange
                icon: mdi:sort-alphabetical-descending
                name: Z-A
                state_content: name
                tap_action:
                  action: perform-action
                  perform_action: input_select.select_option
                  target:
                    entity_id: input_select.todo_list_sort_order
                  data:
                    option: Z to A
            tap_action:
              action: navigate
              navigation_path: /hassio/ingress/XXXXXXXX_wonderful_wino   #INSERT YOUR INGRESS SLUG
          - display_order: none
            type: todo-list
            entity: todo.my_wine
            hide_create: true
        visibility:
          - condition: state
            entity: input_select.todo_list_sort_order
            state: Custom
          - condition: state
            entity: input_boolean.show_rating_card
            state_not: "on"
      - type: grid
        cards:
          - type: heading
            heading_style: subtitle
            heading: Wine List
            icon: mdi:glass-wine
            badges:
              - type: entity
                show_state: true
                show_icon: true
                entity: input_select.todo_list_sort_order
                color: yellow
                state_content: name
                tap_action:
                  action: perform-action
                  perform_action: input_select.select_first
                  target:
                    entity_id: input_select.todo_list_sort_order
                  data: {}
                name: Edit
              - type: entity
                show_state: true
                show_icon: true
                entity: input_select.todo_list_sort_order
                color: deep-orange
                icon: mdi:sort-alphabetical-descending
                name: Z-A
                state_content: name
                tap_action:
                  action: perform-action
                  perform_action: input_select.select_option
                  target:
                    entity_id: input_select.todo_list_sort_order
                  data:
                    option: Z to A
            tap_action:
              action: navigate
              navigation_path: /hassio/ingress/XXXXXXXX_wonderful_wino  #INSERT YOUR INGRESS SLUG
          - display_order: alpha_asc
            type: todo-list
            entity: todo.my_wine
            hide_create: true
        visibility:
          - condition: state
            entity: input_select.todo_list_sort_order
            state: A to Z
          - condition: state
            entity: input_boolean.show_rating_card
            state_not: "on"
      - type: grid
        cards:
          - type: heading
            heading_style: subtitle
            heading: Wine List
            icon: mdi:glass-wine
            badges:
              - type: entity
                show_state: true
                show_icon: true
                entity: input_select.todo_list_sort_order
                color: yellow
                state_content: name
                tap_action:
                  action: perform-action
                  perform_action: input_select.select_first
                  target:
                    entity_id: input_select.todo_list_sort_order
                  data: {}
                name: Edit
              - type: entity
                show_state: true
                show_icon: true
                entity: input_select.todo_list_sort_order
                name: A-Z
                icon: mdi:sort-alphabetical-ascending
                state_content: name
                color: lime
                tap_action:
                  action: perform-action
                  perform_action: input_select.select_option
                  target:
                    entity_id: input_select.todo_list_sort_order
                  data:
                    option: A to Z
            tap_action:
              action: navigate
              navigation_path: /hassio/ingress/XXXXXXXX_wonderful_wino  #INSERT YOUR INGRESS SLUG
          - display_order: alpha_desc
            type: todo-list
            entity: todo.my_wine
            hide_create: true
        visibility:
          - condition: state
            entity: input_select.todo_list_sort_order
            state: Z to A
          - condition: state
            entity: input_boolean.show_rating_card
            state_not: "on"
    badges:
      - type: entity
        show_name: true
        show_state: true
        show_icon: true
        entity: todo.my_wine
        icon: mdi:bottle-wine-outline
        color: deep-purple
        name: Unique Wine Count
    cards: []
    theme: Google Dark Theme Condensed


**What is Home Assistant Ingress???**

Ingress is a proxy system built into Home Assistant that provides secure and seamless access to an add-on's web UI from within the Home Assistant frontend. It utilizes Home Assistant's existing authentication and network handling, making it extremely secure which eliminates the need for manual port configuration and direct network exposure of the add-on.

<a name="determining-wonderful-wino-ingress-url"></a>
### Determining Wonderful Wino Ingress URL:

While the default method for access is the **Open Web UI** button (or by enabling it on the Home Assistant Sidebar), the direct Ingress URL may be required for advanced configurations, such as embedding in custom dashboards.

The URL includes a unique identifier, or "slug," for the add-on. This slug, which contains an 8 random hex character portion (e.g., `a0d7b954_wonderful_wino`), is automatically assigned based on the add-on's repository and is not user-configurable.

To determine the exact URL for your installation:

1.  Navigate to **Settings** > **Add-ons** and select **Wonderful Wino**.
    
2.  Click the **Open Web UI** button.
    
3.  Once the add-on's interface has loaded, copy the full URL from your browser's address bar.
    
    The URL will follow this format: `http://[YOUR_HOME_ASSISTANT_IP or HOST]:8123/hassio/ingress/[ADDON_SLUG]`  e.g.  `http://192.168.0.222:8123/hassio/ingress/a1b2c487_wonderful_wino`

**Copy the 8 character randon characters from your slug and paste them  to replace the 8 X's in your Dashboard yaml above in *three places***

Once you determine your URL, you can use this anywhere you want in your own dashboards to navigate to the Wonderful Wino GUI and eliminate the Sidebar if you wish.


<a name="voice-assistant-ai-prompts"></a>
## Voice Assistant AI Prompts:
To make YOUR voice assistant a sommelier, you need to add the role of a wine expert to its prompt. Add this to your current Voice Assistant/LLM prompt. Do edit it if required to meet your needs. 

    Wine Expert Persona:
    - You are a knowledgeable wine expert, but only discuss wine when specifically asked about it, except when food is mentioned. You are then always free to offer up wine pairing information proactively
    - You are aware of global wine regions and their countries, their typical grape varietals and even some of the prominent wineriers and wine-makers.
    
    - Crucially, when asked about my wines or the wine collection or in the wine cellar, you MUST consult the todo.my_wine entity (or its aliases like "wine list" or "wine inventory"). Do not state you lack access; if a wine isn't on the list, clearly state you don't have it.

**Ensure your ToDo is exposed to your AI and consider adding aliases** for the `todo.my_wine` entity compatible with the way you speak.  For example, besides "my wine", I have aliases such as "wine collection, "wine list" and "in the wine fridge".  

 
***If you have made it this far, your Wonderful Wino should be fully up and running, and working with your Voice Assistant.***



### Samba Share Home Assistant Add-on
You may want to consider adding the [Samba Share add-on](https://www.home-assistant.io/common-tasks/os/)  if you don't already have it installed.  

Wonderful Wino stores it SQLite database in share/wwino. The software has a backup feature that will provide a backup into that same folder. For those who would like to take you backup and put it onto other media, the Samba Share Add-on might be the easiest way to accomplish this. 

Also, Wonderful Wino displays a thumbnail of your wine bottle via a URL. If for some reason a thumbnail is not automatically obtained or you simply do not like the image, it is possible to change the URL to something from the web, or to something local via the standard Home Assistant /www/ folder mechanism.
If you wish to create and house your own thumbnails. Simply create a folder called wwino inside www. You can use the Samba Add-on to copy your desired images there. The URL to use for a locally held image should be formatted like this: 

    ''http://<Your HomeAssistant IP>:8123/local/wwino_images/my_wine_image.jpg''


<a name="quick-visual-guide-to-using-wonderful-wino"></a>
# Quick Visual Guide to Using Wonderful Wino
## Adding Wine
Generally the tedium of adding entries to a personal database of any kind often is it's downfall. This is where Wonderful Wino really shines. All the tools make short work of it.

Generally there are 4 ways to add wine to your Wonderful Wino' database.
1. Manually via the Wonderful Wino GUI
2. Vivino-Assisted via the Wonderful Wino GUI
3. Vivino-Assisted via  Chrome Browser Extension
4. Vivino-Assisted via  Android Helper App

### Adding Wine via Wonderful Wino GUI:
![AddWinePanel](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp1.png)

*Wonderful Wino is a Home Assistant Add-on that uses "INGRESS". If you are configured so that you can use Home Assistant outside of your home network, the Wonderful Wino GUI should also work normally anywhere your Home Assistant can.*


<a name="manually-via-wonderful-wino-gui"></a>
### Manually via Wonderful Wino GUI:
![AddWineModal](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp2.png) 
![AWP6](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp6.png)

<a name="vivino-assisted-via-wonderful-wino-gui"></a>
### Vivino-Assisted via Wonderful Wino GUI:
![AddWinePanel3a](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp3a.png)
 ![AWP7](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp7.png)
 
*The most important points to remember when searching Vivino using this method are to include the 4 digits for the vintage, and before grabbing the URL to paste back in WW ensure you have drilled down sufficiently to the specific wines' page.*

<a name="other-tools-for-adding-wine-to-your-database"></a>
## Other Tools for Adding Wine to your Database:
The **Other Tools** button provides access to the Github repositories for the additional tools for adding wine. 

<a name="wonderful-wino-chrome-browser-extension"></a>
### Wonderful Wino Chrome Browser Extension:
If you use the Chrome Browser, with this extension you can add wine to your inventory without ever touching the Wonderful Wino GUI, or Home Assistant. 

Search your wine on Vivino's site using Chrome and drill down to the wine's specific page.
Click the **Red Wine icon** on the extensions bar to bring up the Wonderful Wino Chrome extension with the Vivino URL already pre-populated.

![CBE](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/cbe.png)

 - Confirm (or set) the correct vintage
 - Confirm (or set) your quantity
 - Set a cost Tier if desired
 - Click **Add Wine**.

**Important:** The Wonderful Wino Chrome Browser Extension **will only work on your home network** as it communicates with the Wonderful Wino backend via standard HTTPS POST requests sent to a specific REST API endpoint exposed by the backend's Flask web server.  As 99.9% of the time you will likely be adding wine to your collection at home, this should not be a major limitation.

<a name="wonderful-wino-android-helper-app"></a>
### Wonderful Wino Android Helper App
*This is the most automatic solution of all for those who are lucky enough to have an Android Phone or Tablet fitted with a camera and have the Vivino Android app loaded.*

**Important:** The Wonderful Wino Android Helper app **only works on your Home Network** as it uses the same communication methods as the Chrome Extension.

Upon returning from the store with your latest "wine haul", use the Vivino App to snap a picture of the wine bottle label you just purchased (or search on the Vivino app if you prefer). Vivino will display the wines' page.

Click the **three-dots menu** in upper right corner and select **Share the Wine**.

![VA1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/va1.png)

This will pop up the **Android Sharing Intent Resolver** (fancy name for "where do you want it to go??")

![VA2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/va2.png)

Click the **WWino Android Helper** button

![NewWAH1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wah1.png)

 - Confirm (or set) the correct vintage
 - Confirm (or set) your quantity
 - Set a cost Tier if desired
 - Click **Add Wine**.

<a name="inventory-display-and-filtering-controls"></a>
## Inventory Display and Filtering Controls

![WIDF1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/widf1.png)

At the top of the Wine Inventory are the various Display, Filtering and Sorting controls.

**On Hand - History - All** Allows the display of your On Hand wines, or Wines that you had in the past, but do not any longer, or All of them.

The Wine Types can be filtered by **🍷Red - 🥂White - 🌸Rose' - 🍾Sparkling - 🍰Dessert**

It is also possible to change the direct of the Sort Order, **ascending- descending** and do it by **Name - Varietal - Country - Region - Vintage - Rating - B4B - Quantity**

<a name="wine-inventory-display-panel"></a>
## Wine Inventory Display Panel

![WDA1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wda1a.png)

<a name="actions"></a>
### Actions
On the right side are the "Actions"....
 - Clicking the **Inverted Bottle** indicates that you have
   finished/drank/consumed one bottle of this wine. The quantity on hand will decrement and you will be given an opportunity to Rate the wine. (What better time to rate a wine then right after you finished it?)
   
![WDA2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wda2.png)

 
 - The **Quantity field** gives you a quick read of the number of
   bottles on hand you have of this wine. Alternately you can edit the
   number you have here. For example you scanned a wine but forgot to
   tell the system that you actually bought 3. You can edit the count
   directly via this field.
 - Clicking the 🗑️**Waste Basket** deletes this wine completely from
   your inventory both on hand and in your history. You will have the opportunity to cancel the action.

Clicking ✏️**Pencil** provides a window to edit all details of the wine as well it can be used to do a "Save As" of your wine, say you bought 5 bottles and didn't realize a few of them were another vintage. 

![WDA3](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wda3.png)

<a name="wine-details-and-metrics"></a>
### Wine Details and Metrics
![WD1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wd1.png)

In the center of the screen are the Wine Details. Most of what is displayed is obvious. But I want to discuss the Metrics Quality, Cost and B4B are derived.

 - ⭐**Quality** is based on the Ratings. When you happen to enter a new wine the current community rating (if one exists) is displayed. A community rating is good, but it really means very little if you hate a highly rated wine or love one that gets panned. Therefore whenever you rate a wine your rating is averaged equally with the rating ofthe entire community as a whole. Your rating carries maximum weight.
   
 - 💲**Cost** on a scale of 1-5 dollar signs represents which Cost Tier the wine was in when you purchased it. Cost Tiers are set in the "Settings" window.
 - 🎯**B4B - Bang for your Buck** ranges from -99 to +99 and is based on an algorithm that takes into account the current Quality rating and the cost tier the wine was in.


<a name="thumbnail-image"></a>
### Thumbnail Image
On the left side of the window the image of your wine bottle's label is displayed. However that is not all it does...

**Hover over** the image to see its tasting notes (if you added any).

**Click** the image: 

 - To add  the **Tasting Notes**
 - To view the **Consumption log**
 - To adjust the **thumbnail position** in the window
 - Swap the image URL for another from the web or a local one you provide.

![TNM1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/tnm1.png)

<a name="accessing-settings-and-screen-mode"></a>
## Accessing Settings and Screen Mode
![SM1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/sm1.png)

On the Top far right:
 
 ☀️ **Sun** 🌙 **Moon** for setting **Light** or **Dark** mode

 ⚙️ **Gear** for accessing the **Settings** and **Maintenance** panel

<a name="setting-cost-tiers"></a>
 ### Setting Cost Tiers
![CT](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ct.png)

*Setting Cost Tiers I believe is a straightforward process, but I want to share a couple of quick tips.* - The button top-right (currently "reset" in the image) has double duty. It can be used set the default tiers (which are currently depicted). If changes were made to the cost tiers, the button performs a reset function which allows you to revert to your previous values.
   
 - Within the greater Wonderful Wino GUI, when wanting to set a Cost Tier for a wine, you can hover over the Dollar Sign buttons to see a tool-tip reminding you of its Cost Tier.
   
 - Clicking the **Save** button is required to lock in your changes.

<a name="maintenance-tools"></a>
### Maintenance Tools


![MS1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ms1.png)
 The Help for these are under the **?** button.
![MS2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ms2.png)

One additional comment regarding the **Sync DB to ToDo** button. Wonderful Wino auto-syncs in real time. This button should not normally be needed. It was a tool needed during the building of Wonderful Wino. I decided to include it just in case.

<a name="accessing-your-wine-from-within-home-assistant"></a>
# Accessing Your Wine from within Home Assistant
The "visual" interface to Wonderful Wino inside Home Assistant itself is the My Wine ToDo list. The sections-style Subview Dashboard you created earlier in this document improves on the default ToDo interface by providing sorting logic and a way to access the Wonderful Wino GUI directly. While in sorting, modes it intentionally blocks the ability to manually edit the ToDo list. All wine edits should be made in Wonderful Wino GUI, not in the ToDo list.

<a name="todo-list-controls"></a>
### ToDo List Controls

![TD1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/td1.png)

In the image above...

 - Clicking **Wine List** will navigate you to the Wonderful Wino main GUI

 - Take note of the **Unique Wine Count**. It is derived directly from the `todo.my_wine` entity. The entity holds the total number of lines in the ToDo list as its value which in turn directly correlates to the number of individual wines of the same vintage in your inventory (as the quantity of each wine is stored within the wines' ToDo lists' entry).
 - Clicking on the **Z-A** or **A-Z** will toggle the Sort Order. Clicking on **Edit** will put the list in default Home Assistant order, and as well let you enable the list directly. I would suggest that you avoid editing your ToDo list. If you want to change something do it in the main GUI.

<a name="todo-list-entry-details"></a>
### ToDo List Entry Details
![TD2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/td2.png)

*You may notice that the check box is to* **Complete/Consume** *a Wine and been wondering why the term "Complete" was used. This is a ToDo list after all, and in ToDo-List-Speak, you Complete a Task to remove it from your ToDo list.* I am embarrassed to say I complete more tasks in my wine list than any other ToDo that I have. ;-)

 ![TD3](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/td3.png)

After Consuming a wine you will be given the option to rate it.

Cheers!
 

<a name="how-did-wonderful-wino-come-about"></a>
## How did Wonderful Wino come about?
Wonderful Wino is a Home Assistant Add-on **in which every single line of code was written by AI using Google’s Gemini and ChatGPT** free accounts! A little context, I am a retired computer professional from the high-end commercial print industry, I was not a SW developer, but have I have written a bit of code over the years, mostly in an assortment of now dead languages. I had never written in Python (other than small arduino projects), no Javascript or Kotlin, and despite the several thousands of lines of code in this project, I can honestly say I still haven’t, which is both exciting and scary!  The AI was a consultant to help me hash out the concept and design the GUI. It wrote all of working code, and helped me lock down security. The whole project took about 2 months (working a couple hours each day) from conception to completion using tools and IDE’s (Docker, VSCode, Android Studio, GIT etc.)  - all tools that I never touched before.  I relied on the AI to teach me how to install, configure and use them along the way.

This project started as I enjoy wine and especially with food. Typically I have 20-50 bottles on-hand of various types (although I heavily favor reds). I am certainly no wine expert by any means. I thought it would be great to expose my wine collection to the Home Assistant AI/LLM integration so that it could make real-time expert wine-pairing recommendations using the actual wines in my possession. I quickly realized that one way to accomplish this was my having my wine in a list in Home Assistant some how. The Local ToDo list integration fit the bill. But typing in every single wine that I currently have and purchase in the future would be a manual task that I was not willing to do. So my first thought was to use a barcode scanner. When I purchase wines, I figured I can snap their barcode and populate the ToDo list with its name and vintage, done! So I picked up a product barcode scanner on Ebay. This turned out to be pointless. I actually had working code in hours that would read the barcode and make API calls to several public free food and wine sites. I found out that just about any food product could be scanned and an enormous wealth of data would be returned,  but there was virtually no wine info available out there at least using free or low cost APIs. The barcode reader was a total dead end. 

A glimmer of hope from an old favorite of mine….  Vivino - a popular wine website and app that helps users discover, buy, and enjoy wine. It has a massive database and community ratings. Vivino free website enables people to access their vast database, has community-based ratings, reviews, and other information. Vivino doesn’t have a publicly available API but it does have an incredibly complete database and their website seemed to be consistent and well laid out. Their mobile App provides the ability to snap a picture of a label and provide info about the wine. So with AI as my partner and chief software developer Wonderful Wino was born. If the name Wonderful Wino is familiar to you, you are likely showing you age. The comedian "George Carlin" had a bit around a dysfunctional radio station called "Wonderful Wino", and at about the same time in history, [Frank Zappa](https://www.youtube.com/watch?v=CVEvGMQ2tEI) had a song by the same name. To my knowledge there is no connection between the two.

fj