// CameraFollow.cs — mini kamera takibi (Faz 2'de harita siniri clamp'i eklenecek)
using UnityEngine;

public class CameraFollow : MonoBehaviour
{
    public Transform target;
    public float follow = 8f;
    public Vector3 offset = new Vector3(0, 0, -10);

    void LateUpdate()
    {
        if (!target) return;
        transform.position = Vector3.Lerp(transform.position, target.position + offset, follow * Time.deltaTime);
    }
}
