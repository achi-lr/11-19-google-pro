using System;
using System.Collections.Generic;
using System.IO;
using System.Web.Script.Serialization;

// Only language/theme are saved. This file never contains account credentials.
class Preferences {
    public bool English;
    public bool Dark;
    public static Preferences Load(string path) {
        var result=new Preferences();
        try {
            var data=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(path));
            result.English=data.ContainsKey("language")&&(string)data["language"]=="en";
            result.Dark=data.ContainsKey("theme")&&(string)data["theme"]=="dark";
        }catch(Exception){}
        return result;
    }
    public void Save(string path) {
        var data=new Dictionary<string,string>{{"language",English?"en":"ru"},{"theme",Dark?"dark":"light"}};
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllText(path,new JavaScriptSerializer().Serialize(data));
    }
}
