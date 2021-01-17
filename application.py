
import json
import logging

from flask import Flask, request, render_template, Response
from sqlalchemy import create_engine
from sqlalchemy.sql import text
import geopandas as gpd
from shapely import wkt

# load credentials from a file
#with open("C:/Users/Kyle McCarthy/Documents/GitHub/final-project-kyle-brian/credentials.json", "r") as f_in:
#    pg_creds = json.load(f_in)
#with open("C:/Users/rawnb/Documents/GitHub/MUSA508/final-project-kyle-brian/credentials.json", "r") as f_in:
#    pg_creds = json.load(f_in)


# mapbox
#with open("C:/Users/Kyle McCarthy/Documents/GitHub/final-project-kyle-brian/mapbox_token.json", "r") as mb_token:
#    MAPBOX_TOKEN = json.load(mb_token)["token"]
#with open("C:/Users/rawnb/Documents/GitHub/MUSA508/final-project-kyle-brian/mapbox_token.json", "r") as mb_token:
#    MAPBOX_TOKEN = json.load(mb_token)["token"]

with open("./secrets/credentials.json", "r") as f_in:
    pg_creds = json.load(f_in)

# mapbox
with open("./secrets/mapbox_token.json", "r") as mb_token:
    MAPBOX_TOKEN = json.load(mb_token)["token"]

application = Flask(__name__, template_folder="templates")

# load credentials from JSON file
HOST = pg_creds["HOST"]
USERNAME = pg_creds["USERNAME"]
PASSWORD = pg_creds["PASSWORD"]
DATABASE = pg_creds["DATABASE"]
PORT = pg_creds["PORT"]


def get_sql_engine():
    return create_engine(f"postgresql://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}")


def Zip_Code_names():
    """Gets all zipcodes"""
    engine = get_sql_engine()
    query = text(
        """
        SELECT DISTINCT ZIP_CODE as zip
        FROM sandiego
        ORDER BY 1 ASC
    """
    )
    resp = engine.execute(query).fetchall()
    # get a list of names
    names = [row["zip"] for row in resp]
    return names


def neighborhood_names():
    """Gets all neighborhoods"""
    engine = get_sql_engine()
    query = text(
        """
        SELECT DISTINCT community_area as neighborhoodnames
        FROM( 
        SElECT * 
        FROM sandiego as sd
        WHERE conditionf = 'Poor' or conditionf = 'Fair') san 
        ORDER BY 1 ASC
    """
    )
    resp = engine.execute(query).fetchall()
    # get a list of names
    names = [row["neighborhoodnames"] for row in resp]
    return names


# index page
@application.route("/")
def index():
    """Index page"""
    names = Zip_Code_names()
    return render_template("input.html", nnames=names)


def all_points():
    """Gets earthquake epicenter centroid"""
    engine = get_sql_engine()
    query = text("""
    SELECT ST_SetSRID(ST_MakePoint(s.lng, s.lat), 4326)::geography as geom
    FROM(
        SELECT lng, lat
        FROM sandiego) as s
    """)
    points = gpd.read_postgis(query, con=engine)
    return points


def get_bounds(geodataframe):
    """returns list of sw, ne bounding box pairs"""
    bounds = geodataframe.geom.total_bounds
    bounds = [[bounds[0], bounds[1]], [bounds[2], bounds[3]]]
    return bounds

def get_total_buildings():
    """Get number of buildings in a zipcode"""
    engine = get_sql_engine()
    building_stats = text(
        """
        SELECT COUNT(building_name) as num_buildings
        FROM(
        SELECT building_name, conditionf
        FROM sandiego as f
        WHERE conditionf = 'Poor' or conditionf = 'Fair') as a
    """
    )
    resp = engine.execute(building_stats).fetchone()
    return resp["num_buildings"]




def get_num_buildings(neighborhood):
    """Get number of buildings in a zipcode"""
    engine = get_sql_engine()
    building_stats = text(
        """
        SELECT COUNT(building_name) as num_buildings
        FROM(
          SELECT conditionf, community_area, building_name
        FROM sandiego as f
        WHERE f.community_area = :neighborhood and (conditionf = 'Poor' or conditionf = 'Fair')) as a

    """
    )
    resp = engine.execute(building_stats, neighborhood=neighborhood).fetchone()
    return resp["num_buildings"]


def get_num_earthquakes(nnames):
    """Get number of buildings in a zipcode"""
    engine = get_sql_engine()
    earthquake_stats = text(
        """
        SELECT COUNT(objectid) as num_eq
        FROM(
        SELECT *
        FROM earthquake) as f
        WHERE f.zip= :nnames
    """
    )
    resp = engine.execute(earthquake_stats, nnames=nnames).fetchone()
    return resp["num_eq"]

def get_max_earthquakes(nnames):
    """Get number of buildings in a zipcode"""
    engine = get_sql_engine()
    earthquake_stats = text(
        """
        SELECT MAX(mag) as mag_eq
        FROM(
        SELECT *
        FROM earthquake) as f
        WHERE f.zip= :nnames
    """
    )
    resp = engine.execute(earthquake_stats, nnames=nnames).fetchone()
    return resp["mag_eq"]


def get_centroid(nnames):
    engine = get_sql_engine()
    """Gets earthquake epicenter centroid"""
    query = text(
    """
    SELECT DISTINCT ST_SetSRID(ST_MakePoint(s.lng_zip, s.lat_zip), 4326)::geography as geom
    FROM( 
        SELECT lng_zip, lat_zip, ZIP_CODE
        FROM sandiego) as s
    WHERE ZIP_CODE = :nnames
    """
    )
    resp = engine.execute(query, nnames=nnames).fetchone()
    return resp["geom"]


def total_damage(nnames): 
    engine = get_sql_engine()
    query = text( 
        """ 
    SELECT ROUND(SUM(damage.damagecosts), 2) as sum_damage, ROUND(AVG(damage.damagecosts), 2) as avg_damage
    FROM(
        SELECT total_req, conditionf, building_name, 
        (multiplier * total_req * NormalV) as damagecosts, distance, geom :: geometry as geom
        FROM( 
        SELECT
            CASE WHEN distance < 10000 THEN .8
                 WHEN distance >= 10000 and distance < 30000 THEN .4
                 WHEN distance >= 30000 and distance < 600000 THEN .2
                 WHEN distance >= 60000 and distance < 120000 THEN .1
                 ELSE .05 END as multiplier, 
            lat, lng, NormalV, total_req, conditionf, building_name, distance, geom
            FROM( 
            SELECT  ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography as geom, ST_Distance(:nnames, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) as distance,
            lat, lng, NormalV, total_req, conditionf, building_name
                FROM(
                SELECT lat, lng, NormalV, total_req, conditionf, building_name
                    FROM sandiego as sd
                    where conditionf = 'Poor' or conditionf = 'Fair')as q1)as q2)as q3 ) as damage

        """
        )
    resp = engine.execute(query, nnames = nnames).fetchone()
    return resp["sum_damage"]

def total_n_damage(nnames, neighborhood): 
    engine = get_sql_engine()
    query = text( 
        """ 
    SELECT ROUND(SUM(damage.damagecosts), 2) as sum_damage, ROUND(AVG(damage.damagecosts), 2) as avg_damage, community_area
    FROM(
        SELECT total_req, conditionf, building_name, 
        (multiplier * total_req * NormalV) as damagecosts, distance, geom :: geometry as geom, community_area
        FROM( 
        SELECT
            CASE WHEN distance < 10000 THEN .8
                 WHEN distance >= 10000 and distance < 30000 THEN .4
                 WHEN distance >= 30000 and distance < 600000 THEN .2
                 WHEN distance >= 60000 and distance < 120000 THEN .1
                 ELSE .05 END as multiplier, 
            lat, lng, NormalV, total_req, conditionf, building_name, distance, geom, community_area
            FROM( 
            SELECT  ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography as geom, ST_Distance(:nnames, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) as distance,
            lat, lng, NormalV, total_req, conditionf, building_name, community_area
                FROM(
                SELECT lat, lng, NormalV, total_req, conditionf, building_name, community_area
                    FROM sandiego as sd
                    WHERE :neighborhood = community_area and (conditionf = 'Poor' or conditionf = 'Fair'))as q1)as q2)as q3 ) as damage
                    GROUP BY 3 

        """
        )
    resp = engine.execute(query, nnames = nnames, neighborhood = neighborhood).fetchone()
    return resp["sum_damage"]

def avg_n_damage(nnames, neighborhood): 
    engine = get_sql_engine()
    query = text( 
        """ 
    SELECT ROUND(SUM(damage.damagecosts), 2) as sum_damage, ROUND(AVG(damage.damagecosts), 2) as avg_damage, community_area
    FROM(
        SELECT total_req, conditionf, building_name, 
        (multiplier * total_req * NormalV) as damagecosts, distance, geom :: geometry as geom, community_area
        FROM( 
        SELECT
            CASE WHEN distance < 10000 THEN .8
                 WHEN distance >= 10000 and distance < 30000 THEN .4
                 WHEN distance >= 30000 and distance < 600000 THEN .2
                 WHEN distance >= 60000 and distance < 120000 THEN .1
                 ELSE .05 END as multiplier, 
            lat, lng, NormalV, total_req, conditionf, building_name, distance, geom, community_area
            FROM( 
            SELECT  ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography as geom, ST_Distance(:nnames, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) as distance,
            lat, lng, NormalV, total_req, conditionf, building_name, community_area
                FROM(
                SELECT lat, lng, NormalV, total_req, conditionf, building_name, community_area
                    FROM sandiego as sd
                    WHERE :neighborhood = community_area and (conditionf = 'Poor' or conditionf = 'Fair'))as q1)as q2)as q3 ) as damage
                    GROUP BY 3 

        """
        )
    resp = engine.execute(query, nnames = nnames, neighborhood = neighborhood).fetchone()
    return resp["avg_damage"]

def avg_damage(nnames): 
    engine = get_sql_engine()
    query = text( 
        """ 
    SELECT ROUND(SUM(damage.damagecosts),2 ) as sum_damage, ROUND(AVG(damage.damagecosts),2) as avg_damage
    FROM(
        SELECT total_req, conditionf, building_name, 
        (multiplier * total_req * NormalV) as damagecosts, distance, geom :: geometry as geom
        FROM( 
        SELECT
            CASE WHEN distance < 10000 THEN .8
                 WHEN distance >= 10000 and distance < 30000 THEN .4
                 WHEN distance >= 30000 and distance < 600000 THEN .2
                 WHEN distance >= 60000 and distance < 120000 THEN .1
                 ELSE .05 END as multiplier, 
            lat, lng, NormalV, total_req, conditionf, building_name, distance, geom
            FROM( 
            SELECT  ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography as geom, ST_Distance(:nnames, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) as distance,
            lat, lng, NormalV, total_req, conditionf, building_name
                FROM(
                SELECT lat, lng, NormalV, total_req, conditionf, building_name
                    FROM sandiego as sd 
                    where conditionf = 'Poor' or conditionf = 'Fair')as q1)as q2)as q3 ) as damage

        """
        )
    resp = engine.execute(query, nnames = nnames).fetchone()
    return resp["avg_damage"]




def damaged(nnames): 
    engine = get_sql_engine()
    query = text( 
        """ 
        SELECT zip.geom, CAST(avg(damage.multiplier * damage.total_req * damage.NormalV) AS INT) as damaged_avg, CAST(sum(damage.multiplier * damage.total_req * damage.NormalV) AS INT) as damaged_sum,
        sum(total_req) as assets_value, CAST(zip.zip AS INT) as zip 
        FROM( 
        SELECT
            CASE WHEN distance < 5000 THEN .8
                 WHEN distance >= 5000 and distance < 15000 THEN .4 
                 WHEN distance >= 1500 and distance < 30000 THEN .2
                 WHEN distance >= 30000 and distance < 60000 THEN .1 
                 ELSE 0.05 END as multiplier, 
            lat, lng, NormalV, total_req, conditionf, building_name, distance, geom, zip_code
            FROM( 
            SELECT  ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography as geom, ST_Distance(:nnames :: geography, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) as distance,
            lat, lng, NormalV, total_req, conditionf, building_name,zip_code
                FROM(
                SELECT lat, lng, NormalV, total_req, conditionf, building_name, zip_code
                    FROM sandiego1 as sd
                    WHERE conditionf = 'Fair' or conditionf = 'Poor')as q1)as q2) as damage
            INNER JOIN( 
            SELECT * 
            FROM zip_poly as zip) as zip  
            ON ROUND(zip.zip, 0)::text = damage.zip_code 
            GROUP BY 1, 5
            ORDER BY damaged_sum DESC

        """
        )
    resp = engine.execute(query, nnames = nnames).fetchall()
    buildings = gpd.read_postgis(query, con=engine, params={"nnames": nnames})
    return buildings


@application.route("/zip", methods=["GET"]) #Display a map of all zip codes as polygons with numbers summarized for each
def vacant_viewer():
    """Test for form"""
    name = request.args["zipcode"]
    centroid = get_centroid(name)  # Returns zip centroids as geometry 
    buildings = damaged(centroid)  # Returns all calculations for buildings ---- Page 3
    bounds = get_bounds(all_points())

    # generate interactive map
    map_html = render_template(
        "geojson_map_poly.html",
        geojson_str=buildings.to_json(),
        bounds=bounds,
        center_lng=(bounds[0][0] + bounds[1][0]) / 2,
        center_lat=(bounds[0][1] + bounds[1][1]) / 2,
        mapbox_token=MAPBOX_TOKEN,
    )
    return render_template(
        "vacant.html",
        nname=name,
        map_html=map_html,
        geojson_str=buildings.to_json(),
        buildings= buildings[["zip", "damaged_avg", "damaged_sum", "assets_value"]].values,
        num_buildings = get_total_buildings(), 
        nnames = Zip_Code_names(),
        neighborhoods = neighborhood_names(),
        damagecosts = total_damage(centroid),
        avgcosts = avg_damage(centroid), 
        eq = get_num_earthquakes(name), 
        eq_mag = get_max_earthquakes(name)
    )

def damage(centroid,neighborhood): 
    engine = get_sql_engine()
    query = text( 
        """ 
        SELECT damage.total_req as total_req, damage.conditionf as conditionf, damage.building_name as building_name, zip_code, community_area,
        ROUND((damage.multiplier * damage.total_req * damage.NormalV), 2) as damagecosts, damage.distance, damage.geom, description, building_function, location_description
        FROM( 
        SELECT
            CASE WHEN distance < 5000 THEN .8
                 WHEN distance >= 5000 and distance < 15000 THEN .4 
                 WHEN distance >= 1500 and distance < 30000 THEN .2
                 WHEN distance >= 30000 and distance < 60000 THEN .1 
                 ELSE 0.05 END as multiplier, 
            lat, lng, NormalV, total_req, conditionf, building_name, distance, geom, zip_code, community_area, description, building_function, location_description
            FROM( 
            SELECT  ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography as geom, ST_Distance(:centroid :: geography, ST_SetSRID(ST_MakePoint(lng, lat), 4326)::geography) as distance,
            lat, lng, NormalV, total_req, conditionf, building_name, zip_code, community_area, description, building_function, location_description
                FROM(
                SELECT lat, lng, NormalV, total_req, conditionf, building_name, zip_code, community_area, description, building_function, location_description
                    FROM sandiego1 as sd
                    WHERE community_area = :neighborhood and (conditionf = 'Poor' or conditionf = 'Fair'))as q1)as q2) as damage
                    order by damagecosts DESC

    

        """
        )
    resp = engine.execute(query, centroid = centroid, neighborhood=neighborhood).fetchall()
    buildings = gpd.read_postgis(query, con=engine, params={"centroid": centroid, "neighborhood":neighborhood})
    return buildings

@application.route("/zip/publicb", methods=["GET"]) #Display a map of one specific neighborhood with buildings as points
def Building_viewer():
    """Test for form"""
    code = request.args["epicenter"]
    neighborhood = request.args["ZIP"]
    centroid = get_centroid(code)
    buildings = damage(centroid,neighborhood) # Returns all calculations for buildings ---- Page 3
    # bounds = get_bounds(all_points())
    bounds = get_bounds(buildings)

    # generate interactive map
    map_html = render_template(
        "geojson_map.html",
        geojson_str=buildings.to_json(),
        bounds=bounds,
        center_lng=(bounds[0][0] + bounds[1][0]) / 2,
        center_lat=(bounds[0][1] + bounds[1][1]) / 2,
        mapbox_token=MAPBOX_TOKEN,
    )
    return render_template(
        "public.html",
        nname=code,
        neighborhood=neighborhood,
        map_html=map_html,
        buildings= buildings[["location_description", "building_function", "total_req","damagecosts","conditionf", "description"]].values,
        num_buildings=get_num_buildings(neighborhood),
        nnames = Zip_Code_names(),
        neighborhoods = neighborhood_names(), 
        ncosts = total_n_damage(centroid, neighborhood),
        avgcosts = avg_n_damage(centroid, neighborhood),
        eq = get_num_earthquakes(code), 
        eq_mag = get_max_earthquakes(code)


    )


@application.route("/building_download", methods=["GET"])
def building_download():
    """Download GeoJSON of data snapshot"""
    code = request.args["epicenter2"]
    centroid = get_centroid(code)
    neighborhood = request.args["neighborhood2"]
    buildings = damage(centroid,neighborhood)
    return Response(buildings.to_json(), 200, mimetype="application/json")


# 404 page example
@application.errorhandler(404)
def page_not_found(err):
    """404 page"""
    return f"404 ({err})"


if __name__ == "__main__":
    application.jinja_env.auto_reload = True
    application.config["TEMPLATES_AUTO_RELOAD"] = True
    application.run(debug=True)
