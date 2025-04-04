# Tab Anti-Warping Reborn
A continuation of [Tab Anti Warping +](https://github.com/5axes/tabplus) by 5@xes.  
Originally based on the support blocker code in [UltiMaker Cura](https://github.com/ultimaker/cura).

## So what is it?
**Add circular tabs at the corners of your print to help stop them warping!**  
A targeted and more powerful option than just brims.
- Tabs can be really big if you want. Saves you having to run a big brim around your whole print.
- Multiple layers! The additional layers are generated as a support mesh so they're easy to remove.
  - You can control how far from the model they are. Closer = better hold, *slightly* harder removal. But still not too hard.
- Dish shaped tabs are flat on the bottom, but hollow out as they get higher, leaving just the rim.
  - Has plenty of base area so it holds onto the build plate, but still has plenty of contact with the model without having to remove big bits of solid tab.
  - Easier to remove from the build plate by wedging something under them.
  - Easier to remove from the model (especially with less scarring).

And you don't even need to do the hard work because there's a function to add them automatically!

## How do I use it?
#### Install the plugin, select a model, pick the tool from the toolbar on the left:
![Toolbar icon](data:image/gif;base64,R0lGODdhLAAqAPMAAHR0kwgHP5WUrTg4ZU1MdPT09isqWv///7e3x/n5+/39/c7N2RIRRmhniV1dgunp7iwAAAAALAAqAAAE//DISau9OOvNu/9gKI5kiS0CICyF+S1EIBuIYt94jouA7BMJnTAHsg18MkZBcRgOP4pgjEENGJbOZ+d2EBgGhAEDkHVug4eHgABAsR+2Zpm7waEcgmUC4Wi35nQVCQ8FQTYFCA0OCBI2CQsAi3CATBUoKQiFangPCXJMCmoEKzcPC4RClgAMMwgIkQidoI2OiQCZkA0NApM7FAAGPgwDfSxcoMe5Ag6sVgCGgRIGzQwGo7JxWgXL08I6FWIzBJmUlY8OwT7QcRQCR87Y5aFeSN8U2wTWA/HlD+hJBD6xm6CgAAoEAxCso7RgAAAwpIgQpKOiFyVEBBZo5DdQCAICHNfLPNiVoKSWVA8SylPQcAGtY9lSHahYDqOhCmU+fZwkcMhIATFTfQOVsgayLCkXHJ2YDeenij2FYMSSpQmFpgp2BhXyk6qZSlZnoaBx1KeBNguDWpUTdgE6hxrjyo2LwMsXhVVn6W3A6ouDv4oCO1D0N5+MfWjYHQtrNWUSKgkXIJBMOREVagpf7tDbOJ2PAV5vJBCAxApetp8Y720mI49iRwtYWwm5WK8Ntz4aEAqLQ02zhIW+qn4ZxCQg42qxMo4Kk5Jm5bZX5qQ1PDqRzXmHVpeunY6NCAA7) <-- That one!
#### Set it up the way you like it:
|||
|-|-|
|![Settings panel](data:image/webp;base64,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)|**Size:** Diameter of the tab circle in millimetres.<br>**X/Y Distance:** Sets the X/Y distance from the model for multi-layer / dish support.<br>**Number of layers:** How many layers thick a regular tab will be, or adds layers to a dish-shaped tab.<br>**Use Dish Shape:** Enable/disable the dish shaped tabs I explained up in the first section.<br>**Remove All Tabs:** It is *exactly* what it sounds like.<br>**Add Automatically:** Puts tabs on the outside corners of your model.<br>A small menu pops up letting you choose between more tabs which might overlap or less tabs which might miss a corner.|
#### Add tabs:
If you'd rather do things manually, that's cool (and I'm with you about half the time). With a model selected, the tool active and your settings dialed in, just click on your model where you want a tab. It's that easy! You don't even have to click the bottom of it, click anywhere on its height and the tab will be created on the build plate.
#### Remove tabs:
Accidentally click the wrong spot? Change your mind? Want practice placing them? That's fine, with the tool active just click any existing tab and it will be removed. Or with any of Cura's other tools active just click it to select it then press delete. Or for when it doesn't matter what tool you're in, just right click the tab and click *Delete Selected*.
#### Move tabs:
For that you need to use Cura's built in move tool. Just hold Ctrl and click on something and it'll switch you to that. If you use the *Add Automatically* button, that switches to the move tool. Once you're in the move tool, just click and drag them. Or click the tab and some arrows will appear on the tab in the 3D view and you can click and drag those.
## Want to say hi? Got an idea? Found a bug I haven't?
**I want to hear it!** Just swing by the [the GitHub repo](https://github.com/Slashee-the-Cow/TabAntiWarpingReborn) and go to discussions, or issues.
## What are the latest updates?
### v1.0.0: Initial release
#### What's new?
- Automatically adding tabs now has two options: more tabs (which might overlap) or fewer tabs (which might miss some points). On a lot of models it won't make much difference either way. If you're not sure, go for more.
- Input validation in the tool's control panel now tells you if any of your settings are invalid (and won't let you create tabs if they are invalid).
- The control panel should feel a lot more responsive now.
- Error/status messages are more descriptive because I want you to know *why* it's doing something, not just that it is.
- Should stop you creating tabs that would go outside the build area.
#### What's fixed?
- A bunch of bugs.
- You can't try creating a tab with invalid settings now (could cause a crash before).
- The *Remove All Tabs* button should now only remove tabs and not other support meshes (like if you created some with [Custom Supports Reborn](https://github.com/Slashee-the-Cow/CustomSupportsReborn) - shameless plug).
- Redid the internal layout of the user interface so it should handle things like small window sizes better.
- Will no longer create a tab if Cura miscalculates the click position seriously.
- Added more checks to make sure Cura's settings are what they need to be to handle the requirements of some tab settings.
- Optimised the code a little bit where I could.
#### What's different?
- I've updated everything to make sure it works in the latest versions of Cura.
- The "capsule" tab type has been renamed to "dish".
- Renamed everything in the plugin, inside and out. This means you can have this and another version installed side by side if you want.
- Changed the icon in the toolbar so if you have another version installed you can tell them apart.
#### What's gone?
I did take a couple of features out of the previous incarnation.
- Removed support for Qt 5 to reduce maintenance workload. This means the minimum Cura version required is now 5.0.
- Took out the "Set on adhesion area" setting. It was confusing, a little complicated, and I'm not sure it worked that well anyway.
- There were a few post-processing scripts which I don't think Cura could access anyway, and didn't seem particularly useful, so I took those out.
- There are so many changes the translation files would just completely not work, so I took them out. If you want to translate it, get in touch!
## Known Issues?
- Changes settings related to support so it's not necessarily appropriate for models that need support.
This is required to make sure the tabs don't become part of the model and are printed before it.
- The *Remove All Tabs* button might not remove all the tabs any more, depending on what's happened since the tabs were created.
This is a side effect of making it not remove support meshes which aren't tabs.
- Sometimes Cura miscalculates the click position for creating a new tab.
I prevented the more extreme circumstances but it can still get it wrong sometimes.
As far as I can tell this is an issue with Cura (though I'd really love it if someone showed me it isn't :D) and not something I can fix on my end.
You can safely delete any tabs in the wrong place.
- It's possible to change settings from the optimal defaults set when creating a tab. Please don't.