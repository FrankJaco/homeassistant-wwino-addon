## Home Assistant Add-on: Wonderful Wino

![Supports aarch64 Architecture](https://img.shields.io/badge/aarch64-yes-green.svg) ![Supports amd64 Architecture](https://img.shields.io/badge/amd64-yes-green.svg) ![Supports armhf Architecture](https://img.shields.io/badge/armhf-yes-green.svg) ![Supports armv7 Architecture](https://img.shields.io/badge/armv7-yes-green.svg) ![Supports i386 Architecture](https://img.shields.io/badge/i386-yes-green.svg) 

A personal wine inventory system that can be exposed to the AI/Voice assistant for real-time wine-pairing suggestions and general wine info.

## About

The Wonderful Wino addon provides a user-friendly interface to manage your wine collection within Home Assistant. It can utilize the Local ToDo list integration to maintain a copy of your wine collection complete with essential metadata, making it accessible to your Home Assistant's AI/Voice assistant. 

![mainview](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/gui.png)

We know many "WWinos" out there are familiar with the wwondeful [Vivino](https://www.vivino.com/) website and app.  If you’re not, we highly recommend checking them out. While a Vivino account isn’t required for WW, it’s a fantastic tool that can greatly enhance your wine experience. Wonderful Wino accesses the public areas of the Vivino site to obtain the basic facts about your wine streamlining the task of adding them to your inventory.

Exposing your wine collection to Home Assistant's Voice Assistant (with AI) via the Local ToDo List integration opens up limitless possibilities. When properly configured, your wine facts are just a question away. *Hey Nabu... How many Cabs do I have? What is my oldest vintage? Which wine is rated the highest?* But it can be  so much more than that. It is like having a personal sommelier available at your every whim. (OK, you got to open the bottle yourself!). 

![AI pairing](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/ai.png)

The ToDo list itself provides on the go convenience. The user can see his wine along with essential wine facts in a compact form. Also the user can perform a subset of wine inventory tasks such as informing WWino that you consumed a bottle (which removes it from inventory and permits you to optionally rate the wine you just drank). 

![ToDo](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/todo.png)

Beyond the Wonderful Wino Addon and its GUI, there are currently two additional input tools to help streamline adding wine to your inventory after a visit to your favorite wine merchant:  For those users of the Chrome Browser, there is the [Wonderful Wino Chrome Extension](https://github.com/FrankJaco/wwino-chrome-extension). And for Android phone users who utilize the Vivino App there is the [Wonderful Wino Helper App](https://github.com/FrankJaco/wwino-android-helper). 

![exten
](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/cbe.png)  ![enter image description here](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/aha.png)







## Wonderful Wino  Addon Configuration

![conf](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/conf.png)

**Creating a Home Assistant Long Lived Token:** 
1. Click on your user account profile (bottom of the Home Assistant sidebar on the left)
2. Select the "Security" tab and scroll to its bottom
3. In the **Long-lived access tokens** section and click **Create Token**
4. Name it **WWino** (or anything else you want) and click **OK**
5. Copy and paste it in the configuration HA_LONG_LIVED_TOKEN textbox.

Click **Save** in lower right corner of this panel. 
This completes the Addon configuration. We are now ready to start the addon.

Go back to the Info tab, select your startup options. **Add to Side Bar** is strongly recommended at least at first. Click **Start**. You may want to check the log to ensure a proper first start. It should look something like this...

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

If everything checks out, congratulations, Wonderful Wino is up and running and ready for you to add your wine! You can stop right here. But to really make Wonderful Wino truly wwonderful, we need to configure Home Assistant a wee bit more.

**Local To Do list:**
If you have not done so already, install the [Local ToDo list integration](https://www.home-assistant.io/integrations/local_todo/)  now and make a ToDo list called **My Wine**.

For connectivity between Wonderful Wino and Home Assistant / Local ToDo list a small addition to the configuration.yaml file is required.  You can use the [FileEditor or VSCode addons](https://www.home-assistant.io/common-tasks/os/)  Practice safe "yamling" by checking the configuration in Developer Tools before restarting!

    # Wonderful-Wino Stuff
    rest_command:
      wine_consumed_webhook:
        url: "http://<your HA IP>:5000/api/consume-wine"
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

**Don't forget to put in your Home Assistant's IP address where indicated and restart Home Assistant for the change to take effect!***  Once restarted, you will have a new service called `rest_command.wine_consumed_webhook` that can be used in your scripts and automations. We will add a Home Assistant automation, two Helpers, and a dashboard later to fully enable the ToDo functionality.

 ToDo list, an Automation, two Helpers, a small yaml edit and a dashboard.


**Local ToDo List Integration**

[Local ToDo list integration:](https://www.home-assistant.io/integrations/local_todo/) Permits the wines stored in the Wonderful Wino database to be accessed via a ToDo list. The user can see his wine along with essential wine facts in a compact form. Also the user can perform a subset of wine inventory tasks such as informing WWino that you consumed a bottle (which removes it from inventory and permits you to optionally rate the wine you just drank). 

*If you plan on exposing your wine collection to your voice assistant, the ToDo list is required.*





**Once you have the Local ToDo list integration installed, create a ToDo list for your wine. If you want to keep things easy, use the default name of "My Wine"**




**Home Assistant Voice Assistant  with LLM / AI**

A functioning [Home Assistant Voice Assistant](https://www.home-assistant.io/voice_control/) enhanced with AI. (I personally use the [Google Gemini](https://www.home-assistant.io/integrations/google_generative_ai_conversation/) integration.) When your AI is enabled and properly configured, your wine facts are just a question away. *Hey Nabu,,, How many Cabs do I have? What is my oldest vintage? Which wine is rated the highest?* 




It is like having a personal sommelier available at your every whim. (OK, you got to open the bottle yourself!). **I will discuss AI/LLM prompts to make your voice assistant a wine expert in the general documentation.** 

**Samba Share Home Assistant Addon**

The [Samba Share addon](https://www.home-assistant.io/common-tasks/os/) allows to you store your backup the Wonderful Wino database on another storage medium beyond your Home Assistant server. Also, it makes it possible to override the thumbnail image of your wine bottle to one of your own if desired. 


Click **Save** in lower right corner of this panel. 
This completes the Addon configuration. We are now ready to start the addon.




## ToDo list Automation
When properly configured, your wines along with some of their metadata will be visible in your ToDo list. 


NEED LAST CONSUMED wiNE HELPER and Input. text helper

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

Dashboard stuff here

