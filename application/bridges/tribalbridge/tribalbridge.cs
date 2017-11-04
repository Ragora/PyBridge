$TribalDiscord::ListenAddress = "127.0.0.1"; // Localhost is recommended but any non-localhost address that has no external routing is fine.
$TribalDiscord::ListenPort = 2096; // 2 1337 4u.

function TribalDiscord::onConnectRequest(%this, %address, %socket)
{
    error("TribalDiscord: Received a connection from " @ %address);

    %portPosition = strStr(%address, ":");
    %port = getSubStr(%address, %portPosition + 1, strLen(%address));
    %address = getSubStr(%address, 0, %portPosition);

    if (isObject(%this.currentClient))
    {
        %this.currentClient.disconnect();
        %this.currentClient.delete();
        error("TribalDiscord: Terminated an old connection.");
    }

    %this.currentClient = new TCPObject("TribalDiscordClient", %socket) { class = ConnectionTCP; parent = %this; Address = %address; Port = %port; };
}

function TribalDiscord::send(%this, %data)
{
    if (isObject(%this.currentClient))
    {
        %this.currentClient.send(%data @ "\r\n");
        return;
    }

    //if (%data !$= "HEARTBEAT")
    //    error("TribalDiscord: Attempted to send data when there is no active connection.");
}

function TribalDiscordClient::onLine(%this, %line)
{
    if (%this.currentMessageType $= "")
    {
        %this.currentMessageType = %line;
        return;
    }

    if (%this.currentMessageSender $= "")
    {
        %this.currentMessageSender = %line;
        return;
    }

    if (%this.currentMessageSource $= "")
    {
        %this.currentMessageSource = %line;
        return;
    }

    messageAll('msgAll', "\c5[" @ %this.currentMessageSource @ "]\c4 " @ %this.currentMessageSender @ ": " @ %line);
    %this.currentMessageType = "";
    %this.currentMessageSender = "";
    %this.currentMessageSource = "";
}

function TribalDiscord::receiveDisconnect(%this, %client)
{
    %this.send("DISCONNECT" @ "\n" @ %client.namebase);
}

function TribalDiscord::receiveConnect(%this, %client)
{
    %this.send("CONNECT" @ "\n" @ %client.namebase);
}

function TribalDiscord::receiveMessage(%this, %sender, %message)
{
    %message = trim(%message);
    if (strLen(%message) == 0)
        return;

    %this.send("MESSAGE" @ "\n" @ %sender.namebase @ "\n" @ %message);
}

function TribalDiscord::heartBeat(%this)
{
    %this.send("HEARTBEAT");
    return true;
}

function TribalDiscord::updatePulse(%this)
{
    if (!isObject(%this) || !%this.heartBeat())
    {
        TribalDiscord.disconnect();
        TribalDiscord.delete();
        TribalDiscord::initialize();
        TribalDiscord.updatePulse();
        return;
    }

    if (isEventPending(%this.updateHandle))
        return;
    %this.updateHandle = %this.schedule(32, "updatePulse");
}

//------------------------------------------------------------------------------
// Initialization function. This s`hould be called at server start.
//------------------------------------------------------------------------------
function TribalDiscord_initialize()
{
    if (isObject(TribalDiscord) && TribalDiscord.heartBeat())
        return;

    error("TribalDiscord: Initializing server socket ...");
    %connection = new TCPObject(TribalDiscord);

    %name = %connection.getName();
    if (%name $= "")
        %connection = new TCPObject(TribalDiscord);

    // Janky ass server socket programming!
    %oldAddress = %Host::BindAddress;
    $Host::BindAddress = $TribalDiscord::ListenAddress;
    %connection.listen($TribalDiscord::ListenPort);
    $Host::BindAddress = %oldAddress;

    %connection.updatePulse();
}

package TribalDiscord
{
    function DefaultGame::startMatch(%game)
    {
        parent::startMatch(%game);
        TribalDiscord_initialize();
    }

    function GameConnection::onConnect(%client, %name, %raceGender, %skin, %voice, %voicePitch)
    {
        parent::onConnect(%client, %name, %raceGender, %skin, %voice, %voicePitch);

        // Your kind isn't welcome here.
        if (%client.isAIControlled())
            return;

        if (isObject(TribalDiscord))
            TribalDiscord.receiveConnect(%client);
    }

    function GameConnection::onDrop(%client, %reason)
    {
        parent::onDrop(%client, %reason);

        // I said get out!
        if (%client.isAIControlled())
            return;

        if (isObject(TribalDiscord))
            TribalDiscord.receiveDisconnect(%client);
    }

    function chatMessageAll(%sender, %msgString, %a1, %a2, %a3, %a4, %a5, %a6, %a7, %a8, %a9, %a10)
    {
        parent::chatMessageAll(%sender, %msgString, %a1, %a2, %a3, %a4, %a5, %a6, %a7, %a8, %a9, %a10);

        if (isObject(TribalDiscord))
        {
            // Remove any ~w tagging as they won't work when broadcasted out
            %soundLocation = strStr(%a2, "~w");
            if (%soundLocation != -1)
                %a2 = getSubStr(%a2, 0, %soundLocation);
            TribalDiscord.receiveMessage(%sender, %a2);
        }
    }

    function cannedChatMessageAll(%sender, %msgString, %name, %string, %keys)
    {
        parent::cannedChatMessageAll(%sender, %msgString, %name, %string, %keys);

        if (isObject(TribalDiscord))
        {
            // Remove any ~w tagging as they won't work when broadcasted out
            %soundLocation = strStr(%string, "~w");
            if (%soundLocation != -1)
                %string = getSubStr(%string, 0, %soundLocation);
            TribalDiscord.receiveMessage(%sender, "[" @ %keys @ "] " @ %string);
        }
    }
};

if (!isActivePackage(TribalDiscord))
    activatePackage(TribalDiscord);
