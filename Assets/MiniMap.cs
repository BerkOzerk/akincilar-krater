// MiniMap.cs — ekran kosesinde tam harita + oyuncu konumu noktasi
using UnityEngine;

public class MiniMap : MonoBehaviour
{
    public Transform player;
    public RectTransform panel;   // harita goruntusunun RectTransform'i
    public RectTransform marker;  // oyuncu noktasi
    public float haritaW = 305.736f; // W * SCALE (MapBuilder sabitleriyle eslesmeli)
    public float haritaH = 240f;     // H * SCALE

    void LateUpdate()
    {
        if (!player || !panel || !marker) return;
        float u = (player.position.x + haritaW / 2f) / haritaW;
        float v = (player.position.y + haritaH / 2f) / haritaH;
        // panel center pivot -> merkezden ofset
        marker.anchoredPosition = new Vector2((u - 0.5f) * panel.rect.width, (v - 0.5f) * panel.rect.height);
    }
}
