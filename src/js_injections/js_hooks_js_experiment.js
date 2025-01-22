console.log("Loaded HWPG")

function hookCall(obj, prop) {
    try {
        const originalFunction = obj[prop];
        console.log(`[HWPG] Hooked ${obj}.${prop}`);
        obj[prop] = function(...args) {
            logJson = {type: "log", property: `${obj}.${prop}`, args: args, event: "function"}
            console.log('[HWPG] ' + JSON.stringify(logJson));
            return originalFunction.apply(this, args);
        };
    }
    catch (e) {
        logJson = {type: "error", error: e}
        console.log('[HWPG] ' + JSON.stringify(logJson));
    }
}

function hookConstructor(obj, prop) {
    try {
        const originalFunction = obj[prop];
        console.log(`[HWPG] Hooked ${obj}.${prop}`);
        obj[prop] = function(...args) {
            logJson = {type: "log", property: `${obj}.${prop}`, args: args, event: "constructor"}
            console.log('[HWPG] ' + JSON.stringify(logJson));
            return new originalFunction(args);
        };
    }
    catch (e) {
        logJson = {type: "error", error: e}
        console.log('[HWPG] ' + JSON.stringify(logJson));
    }
}

function hookAssignement(object, property) {
    try {
        let desc = Object.getOwnPropertyDescriptor(object, property);
        console.log(`[HWPG] Hooked ${object}.${property}`);
        function _hookedSetter(value) {
            if (desc === undefined) {
                desc = Object.getOwnPropertyDescriptor(object, property);
                console.log(`[HWPG] Create desc for ${object}.${property} again`);
            }
            logJson = {type: "log", property: `${object}.${property}`, value: value, event: "set"}
            console.log('[HWPG] ' + JSON.stringify(logJson));
            return desc.set.apply(this, arguments);
        }

        function _hookedGetter() {
            if (desc === undefined) {
                desc = Object.getOwnPropertyDescriptor(object, property);
                console.log(`[HWPG] Create desc for ${object}.${property} again`);
            }
            logJson = {type: "log", property: `${object}.${property}`, event: "get"}
            console.log('[HWPG] ' + JSON.stringify(logJson));
            return desc.get.apply(this, arguments);
        }

        Object.defineProperty(object, property, {
            get: _hookedGetter,
            set: _hookedSetter
        })
    }
    catch (e) {
        logJson = {type: "error", error: e}
        console.log('[HWPG] ' + JSON.stringify(logJson));
    }
}


function hookReadOnly(object, property) {
    try {
        let desc = Object.getOwnPropertyDescriptor(object, property);
        console.log(`[HWPG] Hooked ${object}.${property}`);

        function _hookedGetter() {
            if (desc === undefined) {
                desc = Object.getOwnPropertyDescriptor(object, property);
                console.log(`[HWPG] Create desc for ${object}.${property} again`);
            }
            logJson = {type: "log", property: `${object}.${property}`, event: "get"}
            console.log('[HWPG] ' + JSON.stringify(logJson));
            return desc.get.apply(this, arguments);
        }

        Object.defineProperty(object, property, {
            get: _hookedGetter
        })
    }
    catch (e) {
        logJson = {type: "error", error: e}
        console.log('[HWPG] ' + JSON.stringify(logJson));
    }
}

Window.prototype.toString = () => { return "Window"; }
MessageChannel.prototype.toString = () => { return "MessageChannel"; }
hookConstructor(window, "MessageChannel")
hookAssignement(MessageChannel.prototype, "port1")
hookAssignement(MessageChannel.prototype, "port2")

MessagePort.prototype.toString = () => { return "MessagePort"; }
hookCall(MessagePort.prototype, "postMessage")
hookCall(MessagePort.prototype, "start")
hookCall(MessagePort.prototype, "close")
hookAssignement(MessagePort.prototype, "onmessage")
hookAssignement(MessagePort.prototype, "onmessageerror")
// hookAssignement(MessagePort.prototype, "onclose")

// https://www.w3.org/TR/cssom-1/
// MediaList has no working toString.
MediaList.prototype.toString = () => { return "MediaList"; }
hookCall(MediaList.prototype, "appendMedium")
hookCall(MediaList.prototype, "deleteMedium")
hookCall(MediaList.prototype, "item")
hookAssignement(MediaList.prototype, "length")
hookAssignement(MediaList.prototype, "mediaText")

StyleSheet.prototype.toString = () => { return "StyleSheet"; }
hookAssignement(StyleSheet.prototype, "type")
hookReadOnly(StyleSheet.prototype, "href")
hookAssignement(StyleSheet.prototype, "ownerNode")
hookAssignement(StyleSheet.prototype, "parentStyleSheet")
hookAssignement(StyleSheet.prototype, "title")
hookAssignement(StyleSheet.prototype, "media")
hookAssignement(StyleSheet.prototype, "disabled")

CSSStyleSheet.prototype.toString = () => { return "CSSStyleSheet"; }
hookAssignement(CSSStyleSheet.prototype, "ownerRule")
hookAssignement(CSSStyleSheet.prototype, "cssRules")
hookAssignement(CSSStyleSheet.prototype, "rules")
hookCall(CSSStyleSheet.prototype, "insertRule")
hookCall(CSSStyleSheet.prototype, "deleteRule")
hookCall(CSSStyleSheet.prototype, "addRule")
hookCall(CSSStyleSheet.prototype, "removeRule")
hookCall(CSSStyleSheet.prototype, "replace")
hookCall(CSSStyleSheet.prototype, "replaceSync")
hookConstructor(window, "CSSStyleSheet")

StyleSheetList.prototype.toString = () => { return "StyleSheetList"; }
hookCall(StyleSheetList.prototype, "item")
hookAssignement(StyleSheetList.prototype, "length")

// LinkStyle
hookAssignement(ProcessingInstruction.prototype, "sheet")

CSSRuleList.prototype.toString = () => { return "CSSRuleList"; }
hookCall(CSSRuleList.prototype, "item")
hookAssignement(CSSRuleList.prototype, "length")

CSSRule.prototype.toString = () => { return "CSSRule"; }
hookAssignement(CSSRule.prototype, "type")
hookAssignement(CSSRule.prototype, "cssText")
hookAssignement(CSSRule.prototype, "parentRule")
hookAssignement(CSSRule.prototype, "parentStyleSheet")

CSSStyleRule.prototype.toString = () => { return "CSSStyleRule"; }
hookAssignement(CSSStyleRule.prototype, "selectorText")
hookAssignement(CSSStyleRule.prototype, "style")

CSSImportRule.prototype.toString = () => { return "CSSImportRule"; }
hookAssignement(CSSImportRule.prototype, "href")
hookAssignement(CSSImportRule.prototype, "media")
hookAssignement(CSSImportRule.prototype, "styleSheet")

CSSGroupingRule.prototype.toString = () => { return "CSSGroupingRule"; }
hookAssignement(CSSGroupingRule.prototype, "cssRules")
hookCall(CSSGroupingRule.prototype, "insertRule")
hookCall(CSSGroupingRule.prototype, "deleteRule")

CSSPageRule.prototype.toString = () => { return "CSSPageRule"; }
hookAssignement(CSSPageRule.prototype, "selectorText")
hookAssignement(CSSPageRule.prototype, "style")

CSSNamespaceRule.prototype.toString = () => { return "CSSNamespaceRule"; }
hookAssignement(CSSNamespaceRule.prototype, "namespaceURI")
hookAssignement(CSSNamespaceRule.prototype, "prefix")

CSSStyleDeclaration.prototype.toString = () => { return "CSSStyleDeclaration"; }
hookAssignement(CSSStyleDeclaration.prototype, "cssText")
hookAssignement(CSSStyleDeclaration.prototype, "length")
hookCall(CSSStyleDeclaration.prototype, "item")
hookCall(CSSStyleDeclaration.prototype, "getPropertyValue")
hookCall(CSSStyleDeclaration.prototype, "getPropertyPriority")
hookCall(CSSStyleDeclaration.prototype, "setProperty")
hookCall(CSSStyleDeclaration.prototype, "removeProperty")
hookAssignement(CSSStyleDeclaration.prototype, "parentRule")
hookAssignement(CSSStyleDeclaration.prototype, "cssFloat")

HTMLElement.prototype.toString = () => { return "HTMLElement"; }
SVGElement.prototype.toString = () => { return "SVGElement"; }
MathMLElement.prototype.toString = () => { return "MathMLElement"; }
hookReadOnly(HTMLElement.prototype, "style")
hookReadOnly(SVGElement.prototype, "style")
hookReadOnly(MathMLElement.prototype, "style")

hookCall(window, "getComputedStyle")

hookCall(window, "setTimeout")

// CSS.prototype.toString = () => { return "CSS"; }
hookCall(CSS, "escape")
