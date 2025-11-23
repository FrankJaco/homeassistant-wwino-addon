
# Wonderful Wino

A personal wine inventory system that can be exposed to the AI/Voice assistant for real-time wine-pairing suggestions and general wine info.

### Table of Contents

-   [About Wonderful Wino](https://frankjaco.github.io/homeassistant-wwino-addon/#about)
-   [Installation](https://frankjaco.github.io/homeassistant-wwino-addon/#installing-the-wonderful-wino-add-on)
-   [Configuration](https://frankjaco.github.io/homeassistant-wwino-addon/#wonderful-wino-add-on-configuration)
    -   [Creating a Home Assistant Long Lived Token for Wonderful Wino](https://frankjaco.github.io/homeassistant-wwino-addon/#creating-a-home-assistant-long-lived-token-for-wonderful-wino)
    -   [MQTT vs REST - Which should I use?](#mqtt-vs-rest---which-one-should-i-use)
    -   [Starting Wonderful Wino the First Time](https://frankjaco.github.io/homeassistant-wwino-addon/#starting-wonderful-wino-for-the-first-time)
-   [Home Assistant Configuration for Wonderful Wino](https://frankjaco.github.io/homeassistant-wwino-addon/#home-assistant-configuration-for-wonderful-wino)
    -   [Local To Do list](https://frankjaco.github.io/homeassistant-wwino-addon/#local-todo-list)
        -   [Configuration.yaml](https://frankjaco.github.io/homeassistant-wwino-addon/#home-assistant-configurationyaml)
        -   [Helpers](https://frankjaco.github.io/homeassistant-wwino-addon/#create-four-home-assistant-helpers)
        -   [Automation](https://frankjaco.github.io/homeassistant-wwino-addon/#home-assistant-automation)
        - [Script](https://frankjaco.github.io/homeassistant-wwino-addon/#home-assistant-script)
        -   [Dashboard Additions](https://frankjaco.github.io/homeassistant-wwino-addon/#dashboard-additions)
            -   [Wonderful Wino URL using Ingress](https://frankjaco.github.io/homeassistant-wwino-addon/#determining-wonderful-wino-ingress-url)
            -   [Vino SubView Dashboard](https://frankjaco.github.io/homeassistant-wwino-addon/#vino-subview-dashboard)
                -    [Accessing the Vino SubView from your Dashboard](https://frankjaco.github.io/homeassistant-wwino-addon/#accessing-the-vino-subview-from-your-dashboard)
            -   [Entities Wonderful Wino creates in Home Assistant](https://frankjaco.github.io/homeassistant-wwino-addon/#entities-wonderful-wino-creates-in-home-assistant)
    -   [Voice Assistant AI Prompts](https://frankjaco.github.io/homeassistant-wwino-addon/#voice-assistant-ai-prompts)
    -   [Samba Share for offline DB backup and Custom Thumbnails](https://frankjaco.github.io/homeassistant-wwino-addon/#samba-share-home-assistant-add-on)
-   [Using Wonderful Wino](https://frankjaco.github.io/homeassistant-wwino-addon/#quick-visual-guide-to-using-wonderful-wino)
    -   [Adding Wine](https://frankjaco.github.io/homeassistant-wwino-addon/#adding-wine)
        -   [Adding Wine Manually](https://frankjaco.github.io/homeassistant-wwino-addon/#manually-via-wonderful-wino-gui)
        -   [Adding Wine Via Vivino URL](https://frankjaco.github.io/homeassistant-wwino-addon/#vivino-assisted-via-wonderful-wino-gui)
        -   [Other Tools for Adding Wine](https://frankjaco.github.io/homeassistant-wwino-addon/#other-tools-for-adding-wine-to-your-database)
            -   [Android Helper App](https://frankjaco.github.io/homeassistant-wwino-addon/#wonderful-wino-android-helper-app)
            -   [Chrome Browser Extension](https://frankjaco.github.io/homeassistant-wwino-addon/#wonderful-wino-chrome-browser-extension)
    -   [Inventory Display Filtering & Sorting](https://frankjaco.github.io/homeassistant-wwino-addon/#inventory-display-and-filtering-controls)
    -   [Wine Inventory Display Panel](https://frankjaco.github.io/homeassistant-wwino-addon/#wine-inventory-display-panel)
        -   [Actions](https://frankjaco.github.io/homeassistant-wwino-addon/#actions)
        -   [Wine Details and Metrics](https://frankjaco.github.io/homeassistant-wwino-addon/#wine-details-and-metrics)
        -   [Thumbnail Image](https://frankjaco.github.io/homeassistant-wwino-addon/#thumbnail-image)
            -   [Tasting Notes](https://frankjaco.github.io/homeassistant-wwino-addon/#thumbnail-image)
            -   [Consumption Log](https://frankjaco.github.io/homeassistant-wwino-addon/#thumbnail-image)
    -   [Accessing Help, Settings and Screen Mode](https://frankjaco.github.io/homeassistant-wwino-addon/#accessing-help-settings-and-screen-mode)
    -   [Settings and Maintenance Panel](https://frankjaco.github.io/homeassistant-wwino-addon/#settings-and-maintenance-panel)
        -   [Setting Cost Tiers](https://frankjaco.github.io/homeassistant-wwino-addon/#setting-cost-tiers)
        -   [Database Backup and Recovery](https://frankjaco.github.io/homeassistant-wwino-addon/#maintenance-tools)
        -   [Maintenance Tools](https://frankjaco.github.io/homeassistant-wwino-addon/#maintenance-tools)
    -   [Accessing Your Wine from within Home Assistant](https://frankjaco.github.io/homeassistant-wwino-addon/#accessing-your-wine-from-within-home-assistant)
        -   [ToDo List Controls](https://frankjaco.github.io/homeassistant-wwino-addon/#todo-list-controls)
        -   [ToDo List Entry Details](https://frankjaco.github.io/homeassistant-wwino-addon/#todo-list-entry-details)
-   [How did Wonderful Wino come about?](https://frankjaco.github.io/homeassistant-wwino-addon/#how-did-wonderful-wino-come-about)

## About

The Wonderful Wino add-on provides a user-friendly interface to manage your wine collection within Home Assistant. It can utilize the Local ToDo list integration to maintain a copy of your wine collection making it accessible to your Home Assistant’s AI/Voice assistant.

![mainview](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/gui.png)

We know many “WWinos” out there are familiar with the wwondeful  [Vivino](https://www.vivino.com/)  website and app. If you’re not, we highly recommend checking them out. While a Vivino account isn’t required for WW, it’s a fantastic tool that can greatly enhance your wine experience. Wonderful Wino accesses the public areas of the Vivino site to obtain the basic facts about your wine streamlining the task of adding them to your inventory.

Exposing your wine collection to Home Assistant’s Voice Assistant (with AI) via the Local ToDo List integration opens up limitless possibilities. When properly configured, your wine facts are just a question away.  _Hey Nabu… How many Cabs do I have? What is my oldest vintage? Which wine is rated the highest?_  But it can be so much more than that. It is like having a personal sommelier available at your every whim. (OK, you got to open the bottle yourself!).

![AI pairing](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ai.png)

The ToDo list itself provides on-the-go convenience. The user can see his wine along with essential wine facts in a compact form. Also the user can perform a subset of wine inventory tasks such as informing Wonderful Wino’s backend that you consumed a bottle (which removes it from inventory and permits you to optionally rate the wine you just drank).

![ToDo](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/todo.png)

Beyond the Wonderful Wino Add-on and its GUI, there are currently two additional input tools to help streamline adding wine to your inventory after a visit to your favorite wine merchant: For those users of the Chrome Browser, there is the  [Wonderful Wino Chrome Extension](https://github.com/FrankJaco/wwino-chrome-extension). And for Android phone users who utilize the Vivino App there is the  [Wonderful Wino Helper App](https://github.com/FrankJaco/wwino-android-helper).

### Chrome Extension
![CBE](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/cbe.png)

### Android Helper  
![AHA](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/aha.png)

# Installing the Wonderful Wino Add-on:

**Prerequisites:**  You must be running a version of Home Assistant that includes the Supervisor panel. (e.g. Home Assistant OS) and have enabled “Advanced Mode” in your Home Assistant user profile.

**Installation Steps:**  Adding a custom add-on repository is a fairly straightforward process.

1.  **Navigate to the Add-on Store**
    -   Open your Home Assistant frontend.
    -   In the left-hand menu, click on  **Settings**.
    -   From the Settings menu, select  **Add-ons**.
    -   Click the blue  **Add-On Store**  button in the bottom right corner.
2.  **Add the Custom Repository**
    -   Click the  **three-dots menu**  in the top right corner.
    -   Select  **Repositories**.
    -   Paste the repository URL  `https://github.com/FrankJaco/homeassistant-wwino-addon`  and click  **Add**.
    -   Click  **Close**.
3.  **Install the Wonderful Wino Add-on**
    -   After adding the repository, you will likely need to refresh the page for the new addon to appear (by pressing  `Ctrl + R` etc.).
    -   Scroll through the Add-on Store and locate the section titled  **Wonderful Wino Add-on Repository**.
    -   Click on the  **Wonderful Wino**  add-on card to open its information page.
    -   Click the blue  **Install**  button and wait for the installation process to complete. This may take a few minutes.

## Wonderful Wino Add-on Configuration

![conf](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/conf.png)

### Creating a Home Assistant Long Lived Token for Wonderful Wino

1. Click on your  **User Account**  (bottom of the Home Assistant sidebar on the left).
2.  Select the  **Security tab**  at the top of the screen and scroll to its bottom.
3.  In the  **Long-lived access tokens**  section and click  **Create Token**.
4.  Name it  **WWino**  (or anything else you want) and click  **OK**
5.  **Copy and paste**  it to the Configuration tab’s  `HA_LONG_LIVED_TOKEN`  textbox.

### MQTT vs REST - Which one should I use?

On the configuration panel, there is an optional MQTT section. If MQTT Discovery is DISABLED, Wonderful Wino creates entities via REST API, otherwise MQTT is used to create the entities.

**MQTT (Message Queuing Telemetry Transport)** is an efficient, event-driven protocol where a persistent, low-overhead connection with Home Assistant's MQTT Broker is established. When a bottle count changes, the add-on instantly _publishes_ a small message to the broker, which Home Assistant _subscribes_ to, resulting in near real-time updates and better resource usage.

**REST (Representational State Transfer)** Requires the add-on to manually _call_ Home Assistant's HTTP API and send a long-lived token with each request. This is less efficient and requires the add-on to _poll_ (check) for updates, which increases network traffic compared to the instantaneous nature of MQTT.

Wonderful Wino's network traffic load is small in either case. If you are already running MQTT, take advantage of it. If you are not, REST will work just fine. If you want to learn more or potentially install a [MQTT Addon, follow this link.](https://www.home-assistant.io/integrations/mqtt/) The [Mosquitto broker Add-on](https://github.com/home-assistant/addons/tree/master/mosquitto) itself can be found directly in the Home Assistant Add-on Store.

Once you have all your configuration info all set, don't forget to Click  **Save**

### Starting Wonderful Wino for the First Time

Now that the configuration is complete and saved, we are ready to start the add-on.

![su](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/su.png)

-   Go to the  **Info tab**, and select your desired startup options. “Add to Sidebar” is recommended at least at first.
-   Click  **Start**.

_You may want to check the log (by going into the  **Log tab**) to ensure a proper first start. It should look something like this…_

```
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

```

**_If everything checks out, congratulations, Wonderful Wino is up and running and ready for you to add your wine! You could stop right here and use Wonderful Wino as is via its GUI. But to really make Wonderful Wino truly wwonderful, we need to configure Home Assistant a wwee bit more._**

# Home Assistant Configuration for Wonderful Wino

To get the most out of Wonderful Wino, the  [Local ToDo list integration](https://www.home-assistant.io/integrations/local_todo/), and a functioning  [Home Assistant Voice Assistant](https://www.home-assistant.io/voice_control/)  enhanced with Ai are required. (fyi, I personally use the  [Google Gemini](https://www.home-assistant.io/integrations/google_generative_ai_conversation/)  integration and it does a nice job.)

**Quick Summary of Tasks ahead:**
-   Local ToDo list
-   Configuration.yaml edited for communication
-   Helpers, Automation, and script created
-   Dashboard
-   Prompts for AI/Voice Assistant

### Local ToDo list:
If you have not done so already, install the  [Local ToDo list integration](https://www.home-assistant.io/integrations/local_todo/)  now.

Make a ToDo list called  **My Wine**  `todo.my_wine`

(Technically you could call it anything you want, but all the included documentation and yaml etc. are built around that assumption. I recommend starting with “My Wine” first and getting everything up and running before “crossing the beams”.)

### Home Assistant configuration.yaml:

For connectivity between Wonderful Wino and Home Assistant / Local ToDo list a small addition to the configuration.yaml file is required. You can use the  [FileEditor or VSCode add-ons](https://www.home-assistant.io/common-tasks/os/)  for this task.

{% raw %}
```
# Wonderful-Wino Stuff
rest_command:
  wine_consumed_webhook:
    url: "http://<YOUR_HOME_ASSISTANT_IP>:5000/api/consume-wine"
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

```
{% endraw %}

**Don’t forget**  to put in your  **Home Assistant’s IP address**  where indicated!
 _Practice safe “yamling” by checking the configuration in  **Developer Tools**, then  **restart Home Assistant**_.

### Create Four Home Assistant Helpers:

_All four Helpers can be created via the Home Assistant GUI._

Note that each helper is of a different type: **Text** (input_text)  -  **Number** (input_number)  -  **Dropdown** (input_select)  -  **Toggle** (input_boolean)

**Last Consumed Wine**  - **Text** (input_text)  **Helper**

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/lwc.png)

**Taste Rating** - **Number** (input_number) **Helper**

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/trh.png)

**ToDo List Sort Order** - **Dropdown** (Input_Select) **Helper**

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/tdlso.png)

**Show Ratings Card** - **Toggle** (Input_Boolean) **Helper**

![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/src.png)

### Home Assistant Automation:

_Now with the 4 Helpers created, we can create our automation._

The purpose of the automation is for the ToDo list functionality in where the user can “complete / consume” a wine via the ToDo list. The automation will trap that event, provide the user the option of rating the consumed wine, then send the data to the back end to decrement inventory and rate the wine.

**Create a new empty Automation, then click the 3-dots menu and select "Edit in yaml". Copy/Paste the automation in the codebox below and save the automation.** 

{% raw %}
```
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

```
{% endraw %}

### Home Assistant Script:

As you may have noticed, the automation above calls a script. This script submits your wine rating back to the automation and onto Wonderful Wino. It also thanks you if you set a rating with a notification. It then re-hides the wine rating card from view.

**Create a new empty Script, then click the 3-dots menu and select "Edit in yaml". Copy/Paste the Script in the codebox below and save the Script.** 

{% raw %}
```
    alias: "Wonderful-Wino: Submit Taste Rating"
    sequence:
      - data:
          item: "{{ states('input_text.last_consumed_wine') }}"
          rating: "{{ states('input_number.taste_rating') }}"
        action: rest_command.wine_consumed_webhook
      - choose:
          - conditions:
              - condition: not
                conditions:
                  - condition: template
                    value_template: "{{ states('input_number.taste_rating') | int == 0 }}"
            sequence:
              - data:
                  title: 🍷 Wonderful Wino
                  message: >-
                    You rated {{ states('input_text.last_consumed_wine') }} a {{
                    states('input_number.taste_rating') }}! Thanks for sharing.
                action: notify.notify
      - target:
          entity_id:
            - input_boolean.show_rating_card
        action: input_boolean.turn_off
        data: {}
    mode: single
    icon: mdi:send-check
    description: ""
```
{% endraw %}

### Dashboard Additions
**Quick Summary of Tasks ahead:**
-   Determine URL for the Wonderful Wino GUI and its "Ingress Slug"
-   Create "Vino" SubView Dashboard
-   Create Tile card to access the Vino SubView Dashboard

### Determining Wonderful Wino Ingress URL:
Home Assistant Ingress allows add-ons to be securely accessed through the Home Assistant UI without exposing additional ports to the network, routing traffic through Home Assistant’s own reverse proxy. The URL includes a unique identifier, or “slug,” for the add-on. This slug, which contains an 8 random hex character portion (e.g.,  `a0d7b954_wonderful_wino`), is automatically assigned based on the add-on’s repository and is not user-configurable.

While the default method for Add-on access is the  **Open Web UI**  button (or by enabling it on the Home Assistant Sidebar), the direct Ingress URL can be used in custom dashboards and accessing it via a "navigation action". We will be using this later in the "Vino SubView".

**To determine the exact URL for your installation:**

1. Click on Wonderful Wino in the Home Assistant Sidebar.
(If it is not there then: Goto  **Settings**  >  **Add-ons**  and select  **Wonderful Wino**. Then click the  **Open Web UI**  button.)
2.  Once the add-on’s interface has loaded, copy the URL from your browser’s address bar.
    
    The URL will follow this format:
    
    `http://[YOUR_HOME_ASSISTANT_IP_OR_HOSTNAME]:8123/hassio/ingress/[ADDON_SLUG]`
    
    ***for example:***
    
      `http://192.168.0.222:8123/hassio/ingress/a1b2c487_wonderful_wino`
    
Once you determine your URL, you can use this anywhere you want; save it as a bookmark/favorite directly in a browser, or via a dashboard card using the "navigate" action, to access the Wonderful Wino GUI (as we will do in the next section).

**IMPORTANT:  Take note of the 8 random hex characters from *your* slug as they will be needed in the next step!**


### Vino SubView Dashboard
![TODO](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/todo.png)

The Vino Subview provides these functions:

1. Sortable Wine List in a ToDo list card
2. The ability to "consume" a wine by clicking it on the list 
3. Wine Rating interface for wines consumed via the ToDo List method
4. Badges with the total number of bottles in your inventory And the number of “Unique Wines” on hand.
5. One click access to the full Wonderful Wino GUI

**Creating Vino SubView**

**Create an empty Subview on your favorite dashboard:**

![ad](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ad.png)
.
![SV1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/sv1.png)

***Paste the dashboard yaml from the code box below into the yaml window of the Vino subview that you just created. But do not save it just yet as 3 minor edits unique to your installation are required.***



```
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
          rating it. Any other value (0.1 - 5.0 stars) updates the wine's
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
          navigation_path: /hassio/ingress/XXXXXXXX_wonderful_wino # << INGRESS SLUG - Replace X's
      - display_order: none
        item_tap_action: none
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
            icon: mdi:drag
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
          navigation_path: /hassio/ingress/XXXXXXXX_wonderful_wino # << INGRESS SLUG - Replace X's
      - display_order: alpha_asc
        item_tap_action: none      
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
            icon: mdi:drag
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
          navigation_path: /hassio/ingress/XXXXXXXX_wonderful_wino # << INGRESS SLUG - Replace X's
      - display_order: alpha_desc
        item_tap_action: none
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
    entity: sensor.wwino_total_bottles
    name: Total Bottles
    color: deep-purple
  - type: entity
    show_name: true
    show_state: true
    show_icon: true
    entity: sensor.wwino_unique_wines
    color: purple
    name: Total Unique Wines
cards: []
```
![SV2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/sv2.png)

Take note of the 3 lines commented with **INGRESS SLUG**. You will need to edit them with _your_ 8 Hex characters. It is what provides one-click access to the main Wonderful Wino GUI by tapping the "My Wine" Header of the ToDo list. You will need to replace the 8 X’s in **all 3** locations.

***Click SAVE after making all 3 Edits***



### Accessing the Vino SubView from your Dashboard
You will need a way to access the Vino SubView. You can handle this in many ways. For the purpose of this document, I will use a Tile card.

![Tile1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/tile1.png)

Beyond navigation, I like to display the number of unique wines. "Unique wines" are the number of different wines, not the number of bottles. For example if you have 3 bottles of Bogle Phantom 2021 and that is all you have, you have 1 unique wine.

**Add a Tile Card to your desired Dashboard:**

![Tile2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/tile2.png)

How did the Tile card "know" how many unique wines I have? The My Wine ( `todo.my_wine` ) entity contains a count of the number of entries in the ToDo list. When you have more than 1 bottle of the same wine/vintage, the quantity of bottles will be displayed in each ToDo list entry, not each bottle on its own line.

If you prefer, you could use the `sensor.wwino_unique_wines` entity that Wonderful Wino creates instead of `todo.my_wine`. The numbers reported by both these entities should always match. The number of entries in `todo.my_wine` tells you the number of unique wines in your ToDo list; the `sensor.wwino_unique_wines` entity tells you the number of unique wines in your database. Comparing these numbers provides a quick visual confirmation that all is well.

When would these two entities not match?  Ideally never. In the Vino SubView, I have put protections in it to prevent the end user from modifying the ToDo list directly instead of via the Wonderful Wino GUI. But if you were to create and use a different ToDo card and used it to edit the FIRST LINE of a Wonderful Wino ToDo list entry it is possible for the Database and the ToDo list to get out of sync. The good news is you really have to try hard to screw it up, and even if you do, there are tools built into the Wonderful Wino GUI that can assist you getting things back in order.

***That completes the dashboard modifications. You now should have a button/tile on your dashboard that displays the number of unique wines and tapping it will take you to the customized ToDo list, the Vino SubView.***

### Entities Wonderful Wino creates in Home Assistant
```
sensor.wwino_total_bottles
sensor.wwino_unique_wines

sensor.wwino_red_bottles
sensor.wwino_unique_red_wines

sensor.wwino_rose_bottles
sensor.wwino_unique_rose_wines

sensor.wwino_white_bottles
sensor.wwino_unique_white_wines

sensor.wwino_sparkling_bottles
sensor.wwino_unique_sparkling_wines

sensor.wwino_dessert_bottles
sensor.wwino_unique_dessert_wines
```
**BOTTLE** Entities represent the total number of bottles of wine.
**WINE** Entities represent the total number of UNIQUE wines meaning wines of the same name and exact vintage.

## Voice Assistant AI Prompts:

Setting up your Voice Assistant and AI/LLM in Home Assistant is beyond the scope of this document. The instructions below are relevant to all LLM's.

To make YOUR voice assistant a sommelier, you need to add the role of a wine expert to its prompt. Add this to your current Voice Assistant/LLM prompt. Do edit it if required to meet your needs.

```
Wine Expert Persona:
- You are a knowledgeable wine expert, but only discuss wine when specifically asked about it, except when food is mentioned. You are then always free to offer up wine pairing information proactively
- You are aware of global wine regions and their countries, their typical grape varietals and even some of the prominent wineries and wine-makers.

- Crucially, when asked about my wines or the wine collection or in the wine cellar, you MUST consult the todo.my_wine entity (or its aliases like "wine list" or "wine inventory"). Do not state you lack access; if a wine isn't on the list, clearly state you don't have it.

```

**Ensure your ToDo List Entity is exposed to your AI and consider adding aliases compatible with the way you speak.** For example, besides “my wine”, I have aliases such as “wine collection, “wine list” "wine cellar" and “in the wine fridge”.

**_If you have made it this far, your Wonderful Wino should be fully up and running, and working with your Voice Assistant._**

### Samba Share Home Assistant Add-on

You may want to consider adding the  [Samba Share add-on](https://www.home-assistant.io/common-tasks/os/)  if you don’t already have it installed.

Wonderful Wino stores it SQLite database in the Home Assistant standard location: `share/wwino`. The software has a backup feature that will create a backup into that same folder. For those who would like to take your backup and put it onto other media, the Samba Share Add-on might be the easiest way to accomplish this. Simply browse to the `share/wwino` and move the backup elsewhere.

Also, Wonderful Wino displays a thumbnail of your wine bottle via a URL. If for some reason a thumbnail is not automatically obtained or you simply do not like the image, it is possible to change the URL to something from the web, or to something local via the standard Home Assistant `config/www/` "local" folder mechanism. If you wish to create and use your own thumbnails, create the folder `config/www/wwino_images`. You can use the Samba Add-on to copy your desired images there. The URL to use for a **locally held** image should be formatted like this:

`http://<YOUR_HOME_ASSISTANT_IP>:8123/local/wwino_images/my_wine_image.jpg`

# Quick Visual Guide to Using Wonderful Wino

## Adding Wine

Generally the tedium of adding entries to a personal database of any kind is often it’s downfall. This is where Wonderful Wino really shines. All the tools make short work of it.

Generally there are 4 ways to add wine to your Wonderful Wino’ database.

1.  Manually via the Wonderful Wino GUI
2.  Vivino-Assisted via the Wonderful Wino GUI
3.  Vivino-Assisted via Android Helper App
4.  Vivino-Assisted via Chrome Browser Extension

### Adding Wine via Wonderful Wino GUI:

![AddWinePanel](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp1.png)

_Wonderful Wino is a Home Assistant Add-on that uses “INGRESS”. If you are configured so that you can use Home Assistant outside of your home network, the Wonderful Wino GUI should also work normally anywhere your Home Assistant can._

### Manually via Wonderful Wino GUI:

![AddWineModal](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp2.png)

![AWP6](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp6.png)

### Vivino-Assisted via Wonderful Wino GUI:

![AddWinePanel3a](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp3a.png)

![AWP7](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/awp7.png)

_The most important points to remember when searching Vivino using this method are to include the 4 digits for the vintage, and before grabbing the URL to paste back in WW ensure you have drilled down sufficiently to the specific wines’ page._

## Other Tools for Adding Wine to your Database:

The  **Other Tools**  button provides access to the Github repositories for the additional tools for adding wine.

![Ow2aw](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ow2aw.png)

### Wonderful Wino Android Helper App

_This is the most automatic solution of all for those who have an Android Phone or Tablet fitted with a camera and have the Vivino Android app loaded._

**First Launch**

On first launch of the Wonderful Wino Android Helper you will be prompted to enter the IP address of your Home Assistant Server. If you make a mistake or ever need to change the IP, you can access the configuration via the 🔧 Wrench icon on the main screen.

**Using the Android Helper**

Upon returning from the store with your latest “wine haul”, use the Vivino App to snap a picture of the wine bottle label you just purchased (or search on the Vivino app if you prefer). Vivino will display the wines’ page.

Click the  **three-dots menu**  in upper right corner and select  **Share the Wine**.

![VA1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/va1.png)

This will pop up the  **Android Sharing Intent Resolver**

![VA2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/va2.png)

Click the  **WWino Android Helper**  button

![NewWAH1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wah1.png)

-   Confirm (or set) the correct vintage
-   Confirm (or set) your quantity
-   Set a cost Tier if desired
-   Click  **Add Wine**.

**Important:**  The Wonderful Wino Android Helper app  **will only work on your home network**. It communicates with the Wonderful Wino backend via standard HTTPS POST requests sent to a specific REST API endpoint exposed by the backend’s web server. Most of the time you will likely be adding wine to your collection at home, so this should not be a major limitation. BUT...

_I could see a use-case for those people who use the Vivino App at the store to validate the wine before they purchase, and want to immediately add it to their inventory before leaving the store. In a future release I may try to implement a feature that would allow for the caching of the URL's scanned, quantities, and cost tier ratings, that would auto upload to the backend upon returning home._

### Wonderful Wino Chrome Browser Extension:

If you use the Chrome Browser, with this extension you can add wine to your inventory without ever touching the Wonderful Wino GUI, or Home Assistant.

**First Launch**

On first launch of the Wonderful Wino Chrome Browser Extension you will be prompted to enter the IP address of your Home Assistant Server. If you make a mistake or ever need to change the IP, you can access the configuration via the ⚙️ gear icon on the main screen.

**Using the Chrome Browser Extension**

Search your wine on Vivino’s site using Chrome and drill down to the wine’s specific page. Click the  Wondeful Wino **Red Wine icon**  on the extensions bar to bring up the Wonderful Wino Chrome extension with the Vivino URL already pre-populated.

![CBE](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/cbe.png)

-   Confirm (or set) the correct vintage
-   Confirm (or set) your quantity
-   Set a cost Tier if desired
-   Click  **Add Wine**.

_You may have noticed that the pinned Red Wine Glass extension icon at times is grayed-out. That is because the extension is mostly aware of when you are at the Vivino site and drilled down to a specific wine's page before allowing you to attempt to add it to your database._  

**Important:**  The Wonderful Wino Chrome Browser Extension **will only work on your home network**. It communicates with the Wonderful Wino backend via standard HTTPS POST requests sent to a specific REST API endpoint exposed by the backend’s web server. Most of the time you will likely be adding wine to your collection at home, so this should not be a major limitation.

_The combination of having the Vivino website bookmarked in your browser and the Wonderful Wino Chrome Browser Extension pinned are a potent and extremely efficient way of getting your new wine into your database without needing to launch Home Assistant or the Wonderful Wino GUI._


## Inventory Display and Filtering Controls

![WIDF1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/widf1.png)

At the top of the Wine Inventory are the various Display, Filtering and Sorting controls.

**On Hand - History - All**  Allows the display of your On Hand wines, or Wines that you had in the past, but do not any longer, or All of them.

The Wine Types can be filtered by  **🍷Red - 🥂White - 🌸Rose’ - 🍾Sparkling - 🍰Dessert**

It is also possible to change the direct of the Sort Order,  **ascending- descending**  and do it by  **Name - Varietal - Country - Region - Vintage - Rating - B4B - Quantity**

## Wine Inventory Display Panel

![WDA1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wda1a.png)

### Actions

![A1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/a1.png)

On the right side are the “Actions”….

-   Clicking the  **Inverted Bottle**  indicates that you have finished/drank/consumed one bottle of this wine. The quantity on hand will decrement and you will be given an opportunity to Rate the wine. (What better time to rate a wine then right after you finished it?) To rate, select the number of stars by sliding over them. Fine adjust (0.1) is possible via the input number "spinner". 

![A2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/a2.png)
![WDA2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wda2.png)

<br><br>

-   The  **Quantity field**  gives you a quick read of the number of bottles on hand you have of this wine. Alternately you can edit the number you have here. For example you scanned a wine but forgot to tell the system that you actually bought 3. You can edit the count directly via this field.

![A3](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/a3.png)

<br><br>

-   Clicking the 🗑️**Waste Basket**  deletes this wine completely from your inventory both on hand and in your history. You will have the opportunity to cancel the action.

![A5](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/a5.png)

<br><br>

Clicking ✏️**Pencil**  provides a window to edit all details of the wine as well it can be used to do a “Save As” of your wine, say you bought 5 bottles and didn’t realize a few of them were another vintage.

![A4](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/a4.png)
![WDA3](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wda3.png)

### Wine Details and Metrics

![WD1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/wd1.png)

In the center of the screen are the Wine Details. Most of what is displayed is obvious. But I want to discuss the Metrics Quality, Cost and B4B are derived.

-   ⭐**Quality**  is based on the Ratings. When you happen to enter a new wine the current community rating (if one exists) is displayed. A community rating is good, but it really means very little if you hate a highly rated wine or love one that gets panned. Therefore whenever you rate a wine your rating is averaged equally with the rating ofthe entire community as a whole. Your rating carries maximum weight.
    
-   💲**Cost**  on a scale of 1-5 dollar signs represents which Cost Tier the wine was in when you purchased it. Cost Tiers are set in the “Settings” window.
-   🎯**B4B - Bang for your Buck**  ranges from -99 to +99 and is based on an algorithm that takes into account the current Quality rating and the cost tier the wine was in.

### Thumbnail Image

On the left side of the window the image of your wine bottle’s label is displayed. However that is not all it does…

![ANM1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/anm1.png)

**Hover over**  the image to see its tasting notes (if you added any).

**Click**  the image:

-   To add the  **Tasting Notes**
-   To view the  **Consumption log**
-   To adjust the  **thumbnail position**  in the window
-   To adjust the **zoom level** of the thumbnail window
-   To adjust the **vertical tilt** of the thumbnail
-   Swap the image URL for another from the web or a local one you provide.

![TNM1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/tnm1.png)

## Accessing Help, Settings and Screen Mode

![SM1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/sm1.png)

On the Top far right of the main Wonderful Wino screen:

### Help

❓ is for accessing the most current documentation from Wonderful Wino Github site. Note that within various windows you may notice a ? with a circle around it. These will bring up in-app panels with help info.

### Screen Mode

☀️  **Sun**  🌙  **Moon**  for setting  **Light**  or  **Dark**  mode

## Settings and Maintenance Panel

⚙️  **Gear**  for accessing the  **Settings**  and  **Maintenance**  panel

### Setting Cost Tiers

![CT](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ct.png)

_Setting Cost Tiers I believe is a straightforward process, but I want to share a couple of quick tips._  - The button top-right (currently “reset” in the image) has double duty. It can be used set the default tiers (which are currently depicted). If changes were made to the cost tiers, the button performs a reset function which allows you to revert to your previous values.

-   Within the Wonderful Wino GUI, when about to set a Cost Tier for a wine, you can hover over the Dollar Sign buttons to see a tool-tip reminding you of the actual range of the Cost Tier in dollars. 
    
-   Clicking the  **Save**  button is required to lock in your changes.
    

### Maintenance Tools

![MS1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ms1.png)

The Help for these are under the  **?**  button.

![MS2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ms2.png)

One additional comment regarding the  **Sync DB to ToDo**  button. Wonderful Wino auto-syncs in real time. This button should not normally be needed. It was a tool needed during the building of Wonderful Wino. I decided to include it just in case.

# Accessing Your Wine from within Home Assistant

As you learned above, the full Wonderful Wino GUI is available via the Sidebar (if desired) and any place you want it via the ingress slug URL both inside and outside of Home Assistant.

In Home Assistant, the **My Wine** ToDo list serves as the data foundation for Wonderful Wino which enables AI and voice assistant features. The **Vino SubView** dashboard builds on that list to provide a simpler, mobile-friendly way to interact with your wine collection. It’s designed for quick access on smaller screens, letting you view your wines in a compact layout, sort them, mark bottles as consumed when you drink one, and record a taste rating for them, all with your Wonderful Wino database updating automatically. For deeper management and a richer experience, you can jump straight from the Vino SubView to the full Wonderful Wino GUI with a single click. The Vino SubView is a convenient way to work with your **My Wine** list directly inside Home Assistant while keeping everything else just a tap away.

### ToDo List Controls

![TD1](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/td1.png)

In the image above:

-    Clicking **A-Z** or **Z-A** will toggle the list’s alphabetical sort order. Selecting **Edit** switches the list to manual mode, allowing you to reorder items to your liking by **drag-and-drop** using the **three-dot menu**.

-    Clicking **Wine List** opens the full Wonderful Wino main GUI.

-    The Total Bottles Count shows the total number of bottles in your collection. It's entity is `sensor.wwino_total_bottles`.

-    The Total Unique Wine Count shows the total number of individual wines/vintages and comes from the `sensor.wwino_unique_wines`.

### ToDo List Entry Details

![TD2](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/td2.png)

_You may notice that the check box is to_  **Complete/Consume**  _a Wine and been wondering why the term “Complete” was used. This is a ToDo list after all, and in ToDo-List-Speak, you Complete a Task to remove it from your ToDo list._  I am embarrassed to say I complete more tasks in my wine list than any other ToDo that I have. ;-)

![TD3](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/td3.png)

After Consuming a wine you will be given the option to rate it.

Cheers!

## How did Wonderful Wino come about?

Wonderful Wino is a Home Assistant Add-on  **in which every single line of code was written by AI using Google Gemini and ChatGPT**  (free accounts!). A little context, I am a retired computer professional from the high-end commercial print industry, I was not a SW developer, but have written quite a bit of code over the years, mostly in an assortment of now dead languages. I had never written in Python (other than small Arduino projects), no Javascript or Kotlin, and despite the several thousands of lines of code in this project, I can honestly say I still haven’t, which is exciting and scary! The AI was my design consultant to help me hash out the concept and the GUI. It was chief developer and security specialist, as beyond writing all of the working code, it helped me lock down security. The Addon has a Home Assistant Security score of "8" which I believe is the highest obtainable and is Github CodeQL clean. The whole project took a few months (working an hour or two each day). I used tools and IDE’s that I never used before (Docker, VSCode, Android Studio, GIT etc.) relying on the AI to teach me how to install, configure and use them along the way. At times the AI seemed brilliant, other times brain-dead, which over the years could describe many engineers I have known (me included).

This project started as I enjoy wine and especially with food. Typically I have 20-50 bottles on-hand of various types (although I heavily favor reds). I am certainly no wine expert by any means. I thought it would be great to expose my wine collection to the Home Assistant AI/LLM integration so that it could make real-time expert wine-pairing recommendations using the actual wines in my possession. I quickly realized that one way to accomplish this was my having my wine in a list in Home Assistant some how. The Local ToDo list integration fit the bill. But typing in every single wine that I currently have and purchase in the future would be a manual task that I was not willing to do. So my first thought was to use a barcode scanner. When I purchase wines, I figured I can snap their barcode and populate the ToDo list with its name and vintage, done! So I picked up a product barcode scanner on E-bay. This turned out to be pointless. I actually had working code in hours that would read the barcode and make API calls to several public free food and wine sites. I found out that just about any food product could be scanned and an enormous wealth of data would be returned, but there was virtually no wine info available out there at least using free or low cost APIs. The barcode reader was a total dead end for me.

A glimmer of hope from an old favorite of mine…. Vivino - a popular wine website (and app) that helps users discover, buy, and enjoy wine.  Vivino's free website enables people to access their vast database, community-based ratings, reviews, and other general wine information. Vivino doesn’t have a publicly available API but it does have an incredibly complete database and their website seems to be consistent and well laid out. Their mobile App provides the ability to snap a picture of a label and provide info about the wine. So with AI as my partner  Wonderful Wino was born. If the name Wonderful Wino is familiar to you, you are probably showing you age. The comedian [George Carlin](https://www.youtube.com/watch?v=5ubpw63lKOg) had a bit around a dysfunctional radio station called “Wonderful Wino”, and at about the same time in history,  [Frank Zappa](https://www.youtube.com/watch?v=CVEvGMQ2tEI)  had a song by the same name. To my knowledge there is no connection between the two.

fj
