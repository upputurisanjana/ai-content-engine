import streamlit as st
from text_gen import generate_tagline, generate_blog_intro, generate_social_posts
from image_gen import generate_hero_image
from video_gen import generate_promo_video

st.set_page_config(page_title="AI Content Engine", layout="wide")
st.title("AI Content Engine")

with st.sidebar:
    st.header("Product Brief")
    product = st.text_input("Product name", placeholder="e.g. Sparkling Mango Juice")
    audience = st.text_input("Target audience", placeholder="e.g. health-conscious millennials")
    tone = st.text_input("Brand tone", placeholder="e.g. playful / premium / eco")
    clicked = st.button("Generate Campaign", use_container_width=True)

left, right = st.columns([1.2, 1])

if clicked:
    product = product.strip()
    audience = audience.strip()
    tone = tone.strip()
    if not (product and audience and tone):
        st.warning("Please fill in all three fields.")
        st.stop()

    with st.spinner("Generating tagline..."):
        try:
            tagline = generate_tagline(product, audience, tone)
        except Exception as e:
            left.error(f"Tagline failed: {e}")
            st.stop()

    with st.spinner("Writing blog introduction..."):
        try:
            blog_text = generate_blog_intro(product, audience, tone, tagline)
        except Exception as e:
            blog_text = None
            left.error(f"Blog intro failed: {e}")

    with st.spinner("Creating social posts..."):
        try:
            social_json = generate_social_posts(product, tone)
        except Exception as e:
            social_json = None
            left.error(f"Social posts failed: {e}")

    with st.spinner("Generating hero image..."):
        try:
            hero_image_bytes = generate_hero_image(product, tagline, tone)
        except Exception as e:
            hero_image_bytes = None
            right.error(f"Hero image failed: {e}")

    video_bytes = None
    if hero_image_bytes:
        with st.spinner("Rendering promo video (may take 1-2 min)..."):
            try:
                video_bytes = generate_promo_video(hero_image_bytes)
            except Exception as e:
                right.error(f"Video generation failed: {e}")

    with left:
        if tagline:
            st.markdown("### Campaign Tagline")
            st.info(f"**{tagline}**")
            st.caption("Technique: Few-shot prompting")

        if blog_text:
            st.markdown("### Blog Introduction")
            st.markdown(
                f'<div style="background:#f9f9f9;padding:1rem;border-radius:8px">{blog_text}</div>',
                unsafe_allow_html=True,
            )
            st.caption("Technique: Role-based prompting")

        if social_json:
            st.markdown("### Social Media Posts")
            st.caption("Technique: Structured output (JSON)")
            st.markdown("**Twitter / X**")
            st.text_area("", social_json.get("twitter", ""), height=80, key="tw", disabled=True)
            st.caption(f"{len(social_json.get('twitter',''))} / 280 chars")
            st.markdown("**Instagram**")
            st.text_area("", social_json.get("instagram", ""), height=120, key="ig", disabled=True)
            st.caption(f"{len(social_json.get('instagram',''))} / 2200 chars")
            st.markdown("**LinkedIn**")
            st.text_area("", social_json.get("linkedin", ""), height=100, key="li", disabled=True)
            st.caption(f"{len(social_json.get('linkedin',''))} / 700 chars")

    with right:
        if hero_image_bytes:
            st.markdown("### Hero Image")
            st.image(hero_image_bytes, use_container_width=True)
            st.caption("Technique: Image prompt formula (FLUX.2)")

        if video_bytes:
            st.markdown("### Promotional Video")
            st.video(video_bytes)
            st.caption("Technique: Image-to-video (Wan 2.6)")

else:
    left.markdown("*Fill in the sidebar and click **Generate Campaign** to create your assets.*")
