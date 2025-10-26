## Home Assistant Add-on: Wonderful Wino

![Supports aarch64 Architecture](https://img.shields.io/badge/aarch64-yes-green.svg) ![Supports amd64 Architecture](https://img.shields.io/badge/amd64-yes-green.svg) ![Supports armhf Architecture](https://img.shields.io/badge/armhf-yes-green.svg) ![Supports armv7 Architecture](https://img.shields.io/badge/armv7-yes-green.svg) ![Supports i386 Architecture](https://img.shields.io/badge/i386-yes-green.svg) 

A personal wine inventory system that can be exposed to the AI/Voice assistant for real-time wine-pairing suggestions and general wine info.


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

<br>


## Wonderful Wino Add-on Configuration

![conf](https://raw.githubusercontent.com/FrankJaco/homeassistant-wwino-addon/main/resources/conf.png)

**Creating a Home Assistant Long Lived Token: for Wonderful Wino** 
1. Click on your **User Account** (bottom of the Home Assistant sidebar on the left).
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

This concludes the initial configuration of the Wonderful Wino Addon itself. If you want to take it to the next level please consult the **Documentation tab** to forge ahead.  or..... 

### For the best experience, please view the full documentation on our dedicated site:

## [Click Here to Open the Wonderful Wino Documentation](https://frankjaco.github.io/homeassistant-wwino-addon/)



**Cheers!**
