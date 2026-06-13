
import os
os.makedirs("output", exist_ok=True)

# Write the storyboard CSV template
csv_content = '''job_id,title,target_duration_seconds,resolution_w,resolution_h,aspect_ratio,codec,crf,preset
ai-agents-2026,How AI Agents Will Replace 80% of Coding,55,1080,1920,9:16,libx264,18,veryfast

panel_number,scene_description,narration_text,image_filename,image_mode,focal_x,focal_y,allow_upscale,hold_seconds,notes
1,Hero shot - robot at desk,AI agents are about to change everything you know about software development.,hero_robots.jpg,fill,0.5,0.35,false,8,Opening hook - high energy
2,Statistics background,In 2025 Google reported that over 40 percent of new code was written by AI.,stat_bg.png,pad,0.5,0.5,false,7,Cite the stat clearly
3,Developer reaction shot,But what does that actually mean for developers like you?,developer_shock.jpg,fill,0.5,0.3,false,6,Relatable moment
4,Future cityscape,The developers who thrive will be the ones who learn to direct these agents.,city_future.jpg,pad,0.5,0.5,false,8,Aspirational tone
5,Call to action,Start with one task. Automate it. Then stack from there.,cta_bg.png,pad,0.5,0.5,true,6,CTA - urgent
'''

with open("output/storyboard_template.csv", "w") as f:
    f.write(csv_content)

print("CSV written")
