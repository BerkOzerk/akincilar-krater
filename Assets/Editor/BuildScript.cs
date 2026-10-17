// WebGL dogrulama build'i: Unity -batchmode -executeMethod BuildScript.BuildWebGL
// Build ayarlarindaki aktif sahneleri Run/WEBGL_verify altina derler.
using System.Linq;
using UnityEditor;

public static class BuildScript
{
    [MenuItem("Tools/MapBuilder/Build WebGL")]
    public static void BuildWebGL()
    {
        var scenes = EditorBuildSettings.scenes
            .Where(s => s.enabled)
            .Select(s => s.path)
            .ToArray();

        BuildPipeline.BuildPlayer(scenes, "Run/WEBGL_verify", BuildTarget.WebGL, BuildOptions.None);
    }
}
