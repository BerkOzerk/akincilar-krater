// MapBuilder.cs — Akincilar haritasini sahneye kurar (Tools/MapBuilder menusu).
// MCP execute_menu_item ile cagrilir; Build idempotent (tekrar calistirinca temizleyip yeniden kurar).
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public static class MapBuilder
{
    const string TEX = "Assets/Textures/harita_zemin_gb.png";
    const string JSON = "mapdata/uretim/carpisma_unity.json"; // proje kokune goreli (remap_gb.py uretir)
    const float W = 764.34f; // meta sinirlar_m.genislik
    const float H = 600.0f;  // meta sinirlar_m.yukseklik
    const float PPU = 2048f / 764.34f; // 2.67944 -> dunyada 764.34x600 m
    const float SCALE = 0.1f; // oyunsal dunya olcegi: 76.4x60 birim (Pokemon kasabasi orani, kullanici karari)
    const float SPAWN_X = -14.3f;  // Balikesir Gar onu (OSM + UTM 35N donusumu, 13.10.2026)
    const float SPAWN_Y = -194.1f; // dunya koordinati, SCALE oncesi

    [System.Serializable]
    class CarpismaRoot { public List<CarpismaPoly> polygons; }

    [System.Serializable]
    class CarpismaPoly { public float area_m2; public List<Vector2> points; }

    static CarpismaRoot Oku()
    {
        string yol = Path.Combine(Application.dataPath, "..", JSON);
        return JsonUtility.FromJson<CarpismaRoot>(File.ReadAllText(yol));
    }

    static void DokuAyarla()
    {
        var ti = AssetImporter.GetAtPath(TEX) as TextureImporter;
        if (ti == null) { Debug.LogError("Doku yok: " + TEX); return; }
        ti.textureType = TextureImporterType.Sprite;
        ti.spriteImportMode = SpriteImportMode.Single;
        ti.spritePixelsPerUnit = PPU;
        ti.filterMode = FilterMode.Point; // pixel art — sart
        ti.mipmapEnabled = false;
        ti.maxTextureSize = 2048;
        ti.SetPlatformTextureSettings(new TextureImporterPlatformSettings
        {
            name = "WebGL",
            overridden = true,
            maxTextureSize = 2048,
            format = TextureImporterFormat.RGBA32
        });
        ti.SaveAndReimport();
    }

    [MenuItem("Tools/MapBuilder/Build")]
    public static void Build()
    {
        DokuAyarla();
        var spr = AssetDatabase.LoadAssetAtPath<Sprite>(TEX);

        foreach (var n in new[] { "Zemin", "Carpisma" })
            if (GameObject.Find(n) is GameObject eski)
                Object.DestroyImmediate(eski);

        var zemin = new GameObject("Zemin", typeof(SpriteRenderer));
        zemin.GetComponent<SpriteRenderer>().sprite = spr; // Default/order 0
        zemin.transform.localScale = new Vector3(SCALE, SCALE, 1);

        var carpisma = new GameObject("Carpisma");
        carpisma.layer = LayerMask.NameToLayer("Blocking"); // 8
        foreach (var p in Oku().polygons)
        {
            var pc = carpisma.AddComponent<PolygonCollider2D>();
            var pts = new Vector2[p.points.Count];
            for (int i = 0; i < p.points.Count; i++)
                pts[i] = new Vector2((p.points[i].x - W / 2f) * SCALE, (p.points[i].y - H / 2f) * SCALE);
            pc.points = pts;
        }
        Debug.Log("Carpisma: " + carpisma.GetComponents<PolygonCollider2D>().Length + " collider");
        EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
    }

    // nokta 67 poligondan herhangi birinin icinde mi (ray casting)
    static bool Icinde(List<CarpismaPoly> polys, Vector2 n)
    {
        foreach (var p in polys)
        {
            bool ic = false;
            var pts = p.points;
            for (int i = 0, j = pts.Count - 1; i < pts.Count; j = i++)
            {
                float xi = (pts[i].x - W / 2f) * SCALE, yi = (pts[i].y - H / 2f) * SCALE;
                float xj = (pts[j].x - W / 2f) * SCALE, yj = (pts[j].y - H / 2f) * SCALE;
                if ((yi > n.y) != (yj > n.y) &&
                    n.x < (xj - xi) * (n.y - yi) / (yj - yi) + xi)
                    ic = !ic;
            }
            if (ic) return true;
        }
        return false;
    }

    // spawn: Balikesir Gar onu (blok icindeyse yakininda ilk acik alan)
    static Vector2 SpawnBul(CarpismaRoot d)
    {
        var gar = new Vector2(SPAWN_X * SCALE, SPAWN_Y * SCALE);
        if (!Icinde(d.polygons, gar)) return gar;
        for (float r = 5; r < 80; r += 5)
            for (int k = 0; k < 16; k++)
            {
                float a = k * Mathf.PI * 2f / 16f;
                var n = gar + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * r;
                if (!Icinde(d.polygons, n)) return n;
            }
        return Vector2.zero;
    }

    [MenuItem("Tools/MapBuilder/SetupScene")]
    public static void SetupScene()
    {
        Build();
        var d = Oku();

        var hero = AssetDatabase.LoadAssetAtPath<Sprite>(
            "Assets/Tiny RPG Forest/Artwork/sprites/hero/idle/hero-idle-side/hero-idle-side.png");

        GameObject player;
        if (GameObject.Find("Player") is GameObject eskiP)
        {
            player = eskiP;
            var eskiColl = player.GetComponent<BoxCollider2D>();
            if (eskiColl) eskiColl.size = new Vector2(0.32f, 0.32f);
        }
        else
        {
            player = new GameObject("Player", typeof(SpriteRenderer), typeof(BoxCollider2D), typeof(Player));
            player.GetComponent<BoxCollider2D>().size = new Vector2(0.32f, 0.32f);
        }
        player.layer = LayerMask.NameToLayer("Actor"); // 9
        player.transform.localScale = Vector3.one * 0.8f; // 0.8 birim boy (kullanici: 2x buyut)
        player.GetComponent<Player>().speed = 1.2f; // 1.2 birim/sn (~1.5 karakter boyu/sn)
        player.transform.position = SpawnBul(d);
        var sr = player.GetComponent<SpriteRenderer>();
        sr.sprite = hero;
        sr.sortingLayerName = "Actor";
        sr.sortingOrder = 2;

        var cam = Camera.main;
        cam.orthographicSize = 4f; // 0.1x dunyada 8 birim gorus
        var cf = cam.GetComponent<CameraFollow>() ?? cam.gameObject.AddComponent<CameraFollow>();
        cf.target = player.transform;

        // ---- Mini map (sag ust kose) ----
        if (GameObject.Find("Canvas") is GameObject eskiCanvas)
            Object.DestroyImmediate(eskiCanvas);

        var spr2 = AssetDatabase.LoadAssetAtPath<Sprite>(TEX);
        var canvasGO = new GameObject("Canvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
        canvasGO.GetComponent<Canvas>().renderMode = RenderMode.ScreenSpaceOverlay;
        var scaler = canvasGO.GetComponent<CanvasScaler>();
        scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
        scaler.referenceResolution = new Vector2(1920, 1080);

        var panelGO = new GameObject("MiniMapPanel", typeof(RectTransform), typeof(Image));
        panelGO.transform.SetParent(canvasGO.transform, false);
        var panelRT = panelGO.GetComponent<RectTransform>();
        panelRT.anchorMin = panelRT.anchorMax = new Vector2(0, 0); // sol alt kose
        panelRT.pivot = new Vector2(0, 0);
        panelRT.anchoredPosition = new Vector2(12, 12);
        panelRT.sizeDelta = new Vector2(170, 134); // 306x240 orani ~1.275
        panelGO.GetComponent<Image>().color = new Color(0, 0, 0, 0.5f);

        var mapGO = new GameObject("MiniMapImage", typeof(RectTransform), typeof(Image));
        mapGO.transform.SetParent(panelGO.transform, false);
        var mapRT = mapGO.GetComponent<RectTransform>();
        mapRT.anchorMin = mapRT.anchorMax = new Vector2(0.5f, 0.5f);
        mapRT.sizeDelta = new Vector2(160, 126);
        var mapImg = mapGO.GetComponent<Image>();
        mapImg.sprite = spr2;
        mapImg.preserveAspect = true;

        var markGO = new GameObject("PlayerMarker", typeof(RectTransform), typeof(Image));
        markGO.transform.SetParent(mapGO.transform, false);
        var markRT = markGO.GetComponent<RectTransform>();
        markRT.anchorMin = markRT.anchorMax = new Vector2(0.5f, 0.5f);
        markRT.sizeDelta = new Vector2(8, 8);
        markGO.GetComponent<Image>().color = new Color(1f, 0.25f, 0.25f, 1f);

        var mm = canvasGO.AddComponent<MiniMap>();
        mm.player = player.transform;
        mm.panel = mapRT;
        mm.marker = markRT;
        mm.haritaW = W * SCALE;
        mm.haritaH = H * SCALE;

        EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
        Debug.Log("SetupScene tamam, spawn: " + player.transform.position);
    }

    [MenuItem("Tools/MapBuilder/Set Build Scenes")]
    public static void SetBuildScenes()
    {
        EditorBuildSettings.scenes = new[]
        {
            new EditorBuildSettingsScene("Assets/AkincilarSitesi.unity", true)
        };
        Debug.Log("Build sahneleri: AkincilarSitesi (SampleScene disable)");
    }
}
