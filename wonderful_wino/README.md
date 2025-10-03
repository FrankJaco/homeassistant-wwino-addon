## Home Assistant Add-on: Wonderful Wino

![Supports aarch64 Architecture](https://img.shields.io/badge/aarch64-yes-green.svg) ![Supports amd64 Architecture](https://img.shields.io/badge/amd64-yes-green.svg) ![Supports armhf Architecture](https://img.shields.io/badge/armhf-yes-green.svg) ![Supports armv7 Architecture](https://img.shields.io/badge/armv7-yes-green.svg) ![Supports i386 Architecture](https://img.shields.io/badge/i386-yes-green.svg) 

A personal wine inventory system that can be exposed to the AI/Voice assistant for real-time wine-pairing suggestions and general wine info.

## About

The Wonderful Wino addon provides a user-friendly interface to manage your wine collection within Home Assistant. It can utilize the Local ToDo list integration to maintain a copy of your wine collection complete with essential metadata, making it accessible to your Home Assistant's AI/Voice assistant. 


We know many "WWinos" out there are already familiar with the wwondeful [Vivino](https://www.vivino.com/) website and app, but for those who aren't, we do recommend them. Although a Vivino account isn't required, it is truly a great asset that you may wish to consider. Wonderful Wino accesses the public areas of the Vivino site to obtain the basic facts about your wine streamlining the task of adding them to your inventory.

Beyond the Wonderful Wino Addon and its GUI, there are currently two additional tools to help streamline adding wine to your inventory after a visit to your favorite wine merchant: For those users of the Chrome Browser, there is the [Wonderful Wino Chrome Extension](https://github.com/FrankJaco/wwino-chrome-extension). And for Android phone users who utilize the Vivino App there is the [Wonderful Wino Helper App](https://github.com/FrankJaco/wwino-android-helper). More info regarding these additional tools can be found on their respective Github repository pages.

## Wonderful Wino's "Optional" Prerequisites:
1. [Local ToDo list integration:](https://www.home-assistant.io/integrations/local_todo/) Permits the wines stored in the Wonderful Wino database to be accessed via a ToDo list. The user can see his wine along with essential wine facts in a compact form. Also the user can perform a subset of wine inventory tasks such as informing WWino that you consumed a bottle (which removes it from inventory and permits you to optionally rate the wine you just drank.

	**Once you have the Local ToDo list integration installed, create a ToDo list for your wine. If you want to keep things easy, use the default name of "My Wine"**

2.  A functioning [Home Assistant Voice Assistant](https://www.home-assistant.io/voice_control/) enhanced with AI. (I personally use the [Google Gemini](https://www.home-assistant.io/integrations/google_generative_ai_conversation/) integration.) When your AI is enabled and properly configured, your wine facts are just a question away. *How many Cabs do I have? What is my oldest vintage? Which wine is rated the highest?* 
I regularly use it to provide food-wine pairing information using the actual wine within my collection. *Hey Nabu, we are having Veal Saltimbocca with roasted fingerling potatoes as a main course and a charcuterie board for an appetizer. What wine from my collection would pair best with this?*  Or even... *I am serving hamburgers and hot dogs to a bunch of friends. What wine would you recommend that I have in my collection which won’t break the bank, will pair well with the meal?* It is like having a personal sommelier available at your every whim. (OK, you got to open the bottle yourself!). **I will discuss AI/LLM prompts to make your voice assistant a wine expert in the general documentation.** 

 3. **Samba Share addon:** Allows for the easy backup of the Wonderful Wino database. Also, having it makes it possible to override the thumbnail image of your wine bottle to one of your own if desired. 

***Now with the "Optional" Prerequisites out of the way, let's get to the configuration...***


## Addon Configuration:

In the Configuration tab:

**HOME_ASSISTANT_URL:**
http://homeassistant.local:8123  or http://192.168.x.x:8123 
(This should be the **local** URL)

  **HA_LONG_LIVED_TOKEN:**
  *To create a Home Assistant Long Lived Token...*
  
1. Click on your user account profile (bottom of the Home Assistant sidebar on the left)
2. Select the "Security" tab and scroll to its bottom
3. In the **Long-lived access tokens** section and click **Create Token**
4. Name it **WWino** (or anything else you want) and click **OK**
5. Copy the token and paste it in the Wonderful Wino configuration's HA_LONG_LIVED_TOKEN textbox.
(You also could optionally back this up somewhere, but if it is ever lost a new one can be generated and the Wonderful Wino Configuration updated.)

**TODO_LIST_ENTITY_ID**
Set this to the entity ID for your wine's ToDo list. Usually **todo.my_wine**


Click **Save**
This completes the Addon configuration. 

 