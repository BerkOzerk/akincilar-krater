using UnityEngine;

public class Player : MonoBehaviour
{
    public float speed = 6f; // m/s (harita 764x600 m)

    private BoxCollider2D boxCollider;
    private Vector2? hedef; // mouse tiklamasiyla yurunen hedef nokta

    private void Start()
    {
        boxCollider = GetComponent<BoxCollider2D>();
    }

    private void Update()
    {
        if (Input.GetMouseButtonDown(0))
        {
            Vector3 w = Camera.main.ScreenToWorldPoint(Input.mousePosition);
            hedef = new Vector2(w.x, w.y);
        }
    }

    private void FixedUpdate()
    {
        float x = Input.GetAxisRaw("Horizontal");
        float y = Input.GetAxisRaw("Vertical");

        Vector2 yon;
        if (x != 0 || y != 0)
        {
            hedef = null; // klavye, mouse hedefini iptal eder
            yon = new Vector2(x, y).normalized;
        }
        else if (hedef.HasValue)
        {
            Vector2 fark = hedef.Value - (Vector2)transform.position;
            if (fark.magnitude < 0.5f) { hedef = null; return; }
            yon = fark.normalized;
        }
        else return;

        // yon cevirme: scale buyuklugunu koru, yalniz x isaretini degistir
        Vector3 s = transform.localScale;
        if (yon.x > 0.01f) s.x = Mathf.Abs(s.x);
        else if (yon.x < -0.01f) s.x = -Mathf.Abs(s.x);
        transform.localScale = s;

        Vector2 size = boxCollider.bounds.size;
        float adim = speed * Time.fixedDeltaTime;
        int maske = LayerMask.GetMask("Actor", "Blocking");

        // Eksen ayrik hareket: once Y sonra X (duvara kayma).
        // OverlapBox + kendini filtrele — BoxCast origin kendi collider'i icindeyken
        // QueriesStartInColliders yuzunden kendine carpip hareketi kilitliyordu.
        Vector2 hedefPos = (Vector2)transform.position + new Vector2(0, yon.y * adim);
        if (!Engel(hedefPos, size, maske))
            transform.Translate(0, yon.y * adim, 0);

        hedefPos = (Vector2)transform.position + new Vector2(yon.x * adim, 0);
        if (!Engel(hedefPos, size, maske))
            transform.Translate(yon.x * adim, 0, 0);
    }

    bool Engel(Vector2 merkez, Vector2 size, int maske)
    {
        var hits = Physics2D.OverlapBoxAll(merkez, size, 0, maske);
        foreach (var h in hits)
            if (h != boxCollider && !h.isTrigger)
                return true;
        return false;
    }
}
