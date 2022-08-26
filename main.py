# Get the length of the ects-fiches of our university site (in order to find empty or almost empty fiches and see which faculty has the longest ects-fiches)
import requests
import re

from bs4 import BeautifulSoup
from tqdm import tqdm
import pickle

import pandas as pd
import matplotlib.pyplot as plt
import openpyxl as xl

from pprint import pprint


# Get a list containing all trajectories of our university site
def get_trajectories():
    # List of all courses https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/?f=23%2C114%2C124
    #  Note: f=124 means only "Academische opleidingen", 114 for "Master" and 23 for bachelor
    html = requests.get(
        'https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/?s=16&lang=nl&f=23%2C114%2C124').text

    parsed_html = BeautifulSoup(html, features="lxml")
    courses_list_html = parsed_html.find(class_="listCourses")
    courses_list_html_objs = courses_list_html.find_all(class_="wrap")

    trajectories = []

    for course in courses_list_html_objs:
        url = course["href"]

        language = "nl" if url.startswith("/nl/") else "en"
        course_slug = url.split("/")[-2]

        # get the degrees (master and/or bachelor)
        degrees_html = course.find_all("div", class_="value")[1]
        degrees_objs = degrees_html.find_all("li")
        degrees = list([degree.text.lower() for degree in degrees_objs])

        trajectories.append({"language": language, "slug": course_slug, "degrees": degrees})

    return trajectories


def get_courses(url):
    # url: study programme url,
    #  e.g. https://www.uantwerpen.be/en/study/programmes/all-programmes/research-master-philosophy/study-programme/
    try:

        html = requests.get(url)
        if html.status_code != 200:
            print(f"Error getting {url}")
            return []
        html = html.text
        parsed_html = BeautifulSoup(html, features="lxml")

        current_year = parsed_html.find("section", class_="programmes") # first find is the newest year, use find_all and an index to go to another year

        course_title_html_obj = current_year.find_all("h5")
        if len(course_title_html_obj) == 0:
            print(f"Warning: no courses found for {url}")
        courses = []
        for course in course_title_html_obj:
            course_href = course.find("a")["href"]

            course_info = {
                "year": course_href[4:8],
                "id": course_href[9:19],
                "href": course_href,
                "code": course_href[9:13],
                "faculty": course_href[13:16],
                "course": course_href[16:19],
                "name": course.text,
                "page": parsed_html.title.string,
                "url_study_programme": url,
                "url_ects_fiche": f"https://www.uantwerpen.be/ajax/courseInfo{course_href}"
            }

            courses.append(course_info)
        return courses
    except Exception as e:
        print(f"Error: {e}, {url}")
        return []


def is_ok(url):
    return requests.get(url).status_code == 200


def fetch_course_info(trajectories):
    all_courses = []
    num_success = 0
    num_total = 0
    for trajectory in tqdm(trajectories):
        degrees = trajectory["degrees"]
        slug = trajectory["slug"]
        for degree in degrees:
            num_total += 1
            if trajectory["language"] == "nl":
                url1 = f"https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/{slug}/{degree}/studieprogramma/"
                url2 = f"https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/{slug}/over-de-{degree}/studieprogramma/"
                if is_ok(url1):
                    url = url1
                elif is_ok(url2):
                    url = url2
                else:
                    print(f"Error: no url found for {slug} {degree}, {url1}")
                    continue
            else:
                # continue  # Skip english trajectories for now
                # Reason for skip: differenturl formats:
                # https://www.uantwerpen.be/en/study/programmes/all-programmes/epidemiology/about-the-programme/study-programme/
                # https://www.uantwerpen.be/en/study/programmes/all-programmes/research-master-philosophy/study-programme/
                # Check if the url is not 404
                url1 = f"https://www.uantwerpen.be/en/study/programmes/all-programmes/{slug}/study-programme/"
                url2 = f"https://www.uantwerpen.be/en/study/programmes/all-programmes/{slug}/about-the-programme/study-programme/"
                if is_ok(url1):
                    url = url1
                elif is_ok(url2):
                    url = url2
                else:
                    print(f"Error: no url found for {slug} {degree}, {url1}")
                    continue

            traj_courses = get_courses(url)
            if len(traj_courses) > 0:
                num_success += 1

            for course in traj_courses:
                if any(course["id"] in c["id"] for c in all_courses):
                    # course already added (probably overlap with another trajectory)
                    continue
                all_courses.append(course)

    print(f"Success: {num_success}/{num_total}")


    return all_courses


def load_pickle_or_get_from_function(filename, function, *args, **kwargs):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        result = function(*args, **kwargs)
        # Skipping write to picle because max recursion depth error
        # with open(filename, 'wb') as f:
        #     pickle.dump(result, f)
        return result

def get_ects_section(parsed_ects_html, section_number):
    # e.g. section 6 is assessment criteria
    # completed_sections = parsed_ects_html.find_all("div", class_="textblock wysiwyg")
    completed_sections = parsed_ects_html.find_all("div", class_="main")
    if len(completed_sections) < section_number:
        return ""
    return completed_sections[section_number - 1].text

def get_courses_info(courses):
    for course in tqdm(courses):
        try:
            url_params = course["href"]
            html = requests.get(f"https://www.uantwerpen.be/ajax/courseInfo{url_params}").text
            # print(f"Checking url https://www.uantwerpen.be/ajax/courseInfo{url_params}")
            parsed_html = BeautifulSoup(html, features="lxml")

            beautified_course_info = parsed_html.text

            beautified_course_info = re.sub(r'\n+', '\n', beautified_course_info)  # remove double (or more) newlines
            beautified_course_info = re.sub(r'\t', '', beautified_course_info)  # remove tabs
            beautified_course_info = beautified_course_info.replace("\n \n", "\n")  # remove lines containing only a space

            course["ects_length"] = len(beautified_course_info)
            course["ects_text"] = beautified_course_info

            inhoud = get_ects_section(parsed_html, 3)
            course["inhoud"] = inhoud
            course["inhoud_length"] = len(inhoud)

            evalutievormen = get_ects_section(parsed_html, 6)
            course["evalutievormen"] = evalutievormen
            course["evalutievormen_length"] = len(evalutievormen)
        except Exception as e:
            print(f"Error: {e}, {course}")
            continue

    return courses


trajectories = get_trajectories()

all_courses = load_pickle_or_get_from_function('all_courses.pickle', fetch_course_info, trajectories)
all_courses = load_pickle_or_get_from_function('all_courses_extended.pickle', get_courses_info, all_courses)

df = pd.DataFrame(all_courses)
# sort on ects_length
df.sort_values(by=['ects_length'], inplace=True, ascending=True)
df.to_excel("dutch_courses_ects_length.xlsx")

df = df[["faculty", "ects_length"]]
df = df.groupby("faculty").mean()
df.sort_values(by="ects_length", inplace=True)
df.plot(kind="bar")
plt.show()
print(df)

#### example get course info ####
# get_courses_info([{"href": "?id=2022-1071FOWARC&lang=nl"}])
####


#### example get ects section ####
# url_params = "?id=2022-1001WETCHE"
# html = requests.get(f"https://www.uantwerpen.be/ajax/courseInfo{url_params}").text
# parsed_html = BeautifulSoup(html, features="lxml")
# print(get_ects_section(parsed_html, 6))
####

# pprint(get_courses("https://www.uantwerpen.be/nl/studeren/aanbod/alle-opleidingen/rechten-studeren/master/studieprogramma/master-in-de-rechten/"))
